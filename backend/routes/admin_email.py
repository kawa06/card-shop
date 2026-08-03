"""Admin email template management APIs."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import models_email
import schemas_email
from auth import get_current_admin_context
from database import get_db
from services.admin_auth import AdminAccessError, AdminContext, require_permission
from services.db_persist import PersistDep, safe_commit
from services.email_delivery import get_brand_settings, preview_template, send_templated_email
from services.email_events import EMAIL_EVENTS, VARIABLE_ALIASES, get_event_by_template, sample_variables_for_template
from services.email_broadcast import retry_failed_sends
from services.email_rate_limit import check_rate_limit
from services.shipping_email_variables import shipping_variables_for_template
from services.buyback_email_variables import buyback_variables_for_template
from services.buyback_email_auto_send import get_auto_send_settings, update_auto_send_settings
from services.kyc_email_auto_send import (
    get_auto_send_settings as get_kyc_auto_send_settings,
    update_auto_send_settings as update_kyc_auto_send_settings,
)
from services.kyc_email_variables import kyc_variables_for_template
from services.member_email_variables import member_variables_for_template
from services.member_email_auto_send import (
    get_auto_send_settings as get_member_auto_send_settings,
    update_auto_send_settings as update_member_auto_send_settings,
)
from services.loyalty_email_variables import loyalty_variables_for_template
from services.loyalty_email_auto_send import (
    get_auto_send_settings as get_loyalty_auto_send_settings,
    update_auto_send_settings as update_loyalty_auto_send_settings,
)
from services.broadcast_email_variables import broadcast_variables_for_template
from services.broadcast_audience_registry import list_audience_segments

router = APIRouter(
    prefix="/api/admin/email",
    tags=["admin-email"],
    dependencies=[PersistDep],
)


def _require_perm(permission: str):
    def _dep(ctx: AdminContext = Depends(get_current_admin_context)) -> AdminContext:
        try:
            require_permission(ctx, permission)
        except AdminAccessError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        return ctx

    return _dep


@router.get("/brand", response_model=schemas_email.EmailBrandSettingsOut)
def get_brand(
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
    db: Session = Depends(get_db),
):
    return get_brand_settings(db)


@router.put("/brand", response_model=schemas_email.EmailBrandSettingsOut)
def update_brand(
    payload: schemas_email.EmailBrandSettingsUpdate,
    ctx: AdminContext = Depends(_require_perm("admin.email.write")),
    db: Session = Depends(get_db),
):
    brand = get_brand_settings(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(brand, field, value)
    safe_commit(db)
    db.refresh(brand)
    return brand


@router.get("/events")
def list_events(
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
):
    return [
        {
            "event_key": key,
            "template_key": ev.template_key,
            "category": ev.category,
            "description": ev.description,
            "variables": ev.variables,
        }
        for key, ev in EMAIL_EVENTS.items()
    ]


@router.post("/templates", response_model=schemas_email.EmailTemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: schemas_email.EmailTemplateCreate,
    ctx: AdminContext = Depends(_require_perm("admin.email.write")),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(models_email.EmailTemplate)
        .filter(models_email.EmailTemplate.template_key == payload.template_key)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="同じキーのテンプレートが既に存在します")
    tpl = models_email.EmailTemplate(**payload.model_dump())
    db.add(tpl)
    safe_commit(db)
    db.refresh(tpl)
    return tpl


@router.get("/templates", response_model=list[schemas_email.EmailTemplateListItem])
def list_templates(
    category: Optional[str] = Query(None),
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
    db: Session = Depends(get_db),
):
    q = db.query(models_email.EmailTemplate).order_by(
        models_email.EmailTemplate.category,
        models_email.EmailTemplate.template_key,
    )
    if category:
        q = q.filter(models_email.EmailTemplate.category == category)
    return q.all()


@router.get("/templates/{template_key}", response_model=schemas_email.EmailTemplateOut)
def get_template(
    template_key: str,
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
    db: Session = Depends(get_db),
):
    tpl = (
        db.query(models_email.EmailTemplate)
        .filter(models_email.EmailTemplate.template_key == template_key)
        .first()
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="テンプレートが見つかりません")
    return tpl


@router.get("/templates/{template_key}/variables", response_model=schemas_email.EmailTemplateVariablesOut)
def get_template_variables(
    template_key: str,
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
    db: Session = Depends(get_db),
):
    tpl = (
        db.query(models_email.EmailTemplate)
        .filter(models_email.EmailTemplate.template_key == template_key)
        .first()
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="テンプレートが見つかりません")
    event = get_event_by_template(template_key)
    if event:
        variables = event.variables
    elif template_key.startswith("shipping_"):
        variables = shipping_variables_for_template(template_key)
    elif template_key.startswith("buyback_"):
        variables = buyback_variables_for_template(template_key)
    elif template_key.startswith("kyc_") or template_key.startswith("buyback_identity_") or template_key == "buyback_guardian_consent":
        variables = kyc_variables_for_template(template_key)
    elif (
        template_key.startswith("member_")
        or template_key.startswith("login_")
        or template_key.startswith("password_")
        or template_key.startswith("security_")
        or template_key in {"member_register", "member_login_notify", "member_2fa_otp", "member_password_reset", "member_password_change", "member_email_change"}
    ):
        variables = member_variables_for_template(template_key)
    elif (
        template_key.startswith("point_")
        or template_key.startswith("coupon_")
        or template_key.startswith("rank_")
        or template_key.startswith("campaign_")
        or template_key.startswith("loyalty_")
        or template_key in {"coupon_issued", "point_referral"}
    ):
        variables = loyalty_variables_for_template(template_key)
    elif (
        template_key.startswith("broadcast_")
        or template_key in {"announcement_broadcast", "maintenance_notice", "incident_notice", "incident_resolved"}
    ):
        variables = broadcast_variables_for_template(template_key)
    else:
        variables = []
    return schemas_email.EmailTemplateVariablesOut(
        variables=variables,
        aliases=VARIABLE_ALIASES,
        sample=sample_variables_for_template(template_key),
    )


@router.put("/templates/{template_key}", response_model=schemas_email.EmailTemplateOut)
def update_template(
    template_key: str,
    payload: schemas_email.EmailTemplateUpdate,
    ctx: AdminContext = Depends(_require_perm("admin.email.write")),
    db: Session = Depends(get_db),
):
    tpl = (
        db.query(models_email.EmailTemplate)
        .filter(models_email.EmailTemplate.template_key == template_key)
        .first()
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="テンプレートが見つかりません")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tpl, field, value)
    safe_commit(db)
    db.refresh(tpl)
    return tpl


@router.patch("/templates/{template_key}/active", response_model=schemas_email.EmailTemplateOut)
def toggle_template_active(
    template_key: str,
    is_active: bool = Query(...),
    ctx: AdminContext = Depends(_require_perm("admin.email.write")),
    db: Session = Depends(get_db),
):
    tpl = (
        db.query(models_email.EmailTemplate)
        .filter(models_email.EmailTemplate.template_key == template_key)
        .first()
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="テンプレートが見つかりません")
    tpl.is_active = is_active
    safe_commit(db)
    db.refresh(tpl)
    return tpl


@router.get("/buyback/auto-send", response_model=schemas_email.BuybackEmailAutoSendOut)
def get_buyback_auto_send(
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
    db: Session = Depends(get_db),
):
    return schemas_email.BuybackEmailAutoSendOut(settings=get_auto_send_settings(db))


@router.put("/buyback/auto-send", response_model=schemas_email.BuybackEmailAutoSendOut)
def update_buyback_auto_send(
    payload: schemas_email.BuybackEmailAutoSendUpdateIn,
    ctx: AdminContext = Depends(_require_perm("admin.email.write")),
    db: Session = Depends(get_db),
):
    updated = update_auto_send_settings(db, payload.settings)
    safe_commit(db)
    return schemas_email.BuybackEmailAutoSendOut(settings=updated)


@router.get("/kyc/auto-send", response_model=schemas_email.KycEmailAutoSendOut)
def get_kyc_auto_send(
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
    db: Session = Depends(get_db),
):
    return schemas_email.KycEmailAutoSendOut(settings=get_kyc_auto_send_settings(db))


@router.put("/kyc/auto-send", response_model=schemas_email.KycEmailAutoSendOut)
def update_kyc_auto_send(
    payload: schemas_email.KycEmailAutoSendUpdateIn,
    ctx: AdminContext = Depends(_require_perm("admin.email.write")),
    db: Session = Depends(get_db),
):
    updated = update_kyc_auto_send_settings(db, payload.settings)
    safe_commit(db)
    return schemas_email.KycEmailAutoSendOut(settings=updated)


@router.get("/member/auto-send", response_model=schemas_email.MemberEmailAutoSendOut)
def get_member_auto_send(
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
    db: Session = Depends(get_db),
):
    return schemas_email.MemberEmailAutoSendOut(settings=get_member_auto_send_settings(db))


@router.put("/member/auto-send", response_model=schemas_email.MemberEmailAutoSendOut)
def update_member_auto_send(
    payload: schemas_email.MemberEmailAutoSendUpdateIn,
    ctx: AdminContext = Depends(_require_perm("admin.email.write")),
    db: Session = Depends(get_db),
):
    updated = update_member_auto_send_settings(db, payload.settings)
    safe_commit(db)
    return schemas_email.MemberEmailAutoSendOut(settings=updated)


@router.post("/member/users/{user_id}/resend")
def resend_member_email_route(
    user_id: int,
    body: schemas_email.AdminMemberResendEmailIn,
    ctx: AdminContext = Depends(_require_perm("admin.email.write")),
    db: Session = Depends(get_db),
):
    import models
    from services.member_email_registry import get_member_email_event
    from services.member_emails import resend_member_email

    if not get_member_email_event(body.event_key):
        raise HTTPException(status_code=400, detail="不明なイベントキーです")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    ok, err = resend_member_email(
        db,
        event_key=body.event_key,
        user=user,
        verify_url=body.verify_url,
        reset_url=body.reset_url,
    )
    if not ok:
        raise HTTPException(status_code=502, detail=err or "メール送信に失敗しました")
    return {"message": "メールを再送しました", "event_key": body.event_key}


@router.get("/loyalty/auto-send", response_model=schemas_email.LoyaltyEmailAutoSendOut)
def get_loyalty_auto_send(
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
    db: Session = Depends(get_db),
):
    return schemas_email.LoyaltyEmailAutoSendOut(settings=get_loyalty_auto_send_settings(db))


@router.put("/loyalty/auto-send", response_model=schemas_email.LoyaltyEmailAutoSendOut)
def update_loyalty_auto_send(
    payload: schemas_email.LoyaltyEmailAutoSendUpdateIn,
    ctx: AdminContext = Depends(_require_perm("admin.email.write")),
    db: Session = Depends(get_db),
):
    updated = update_loyalty_auto_send_settings(db, payload.settings)
    safe_commit(db)
    return schemas_email.LoyaltyEmailAutoSendOut(settings=updated)


@router.post("/loyalty/users/{user_id}/resend")
def resend_loyalty_email_route(
    user_id: int,
    body: schemas_email.AdminLoyaltyResendEmailIn,
    ctx: AdminContext = Depends(_require_perm("admin.email.write")),
    db: Session = Depends(get_db),
):
    import models
    from services.loyalty_email_registry import get_loyalty_email_event
    from services.loyalty_emails import resend_loyalty_email

    if not get_loyalty_email_event(body.event_key):
        raise HTTPException(status_code=400, detail="不明なイベントキーです")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    ok, err = resend_loyalty_email(db, event_key=body.event_key, user=user)
    if not ok:
        raise HTTPException(status_code=502, detail=err or "メール送信に失敗しました")
    return {"message": "メールを再送しました", "event_key": body.event_key}


@router.get("/broadcast/audiences")
def list_broadcast_audiences(
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
):
    return {"segments": list_audience_segments()}


@router.get("/carriers")
def list_carriers(
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
):
    from services.carrier_registry import CARRIER_REGISTRY

    return [
        {
            "carrier_id": c.carrier_id,
            "display_name": c.display_name,
            "tracking_url_template": c.tracking_url_template,
            "method_keys": sorted(c.method_keys),
        }
        for c in CARRIER_REGISTRY.values()
    ]


@router.post("/templates/{template_key}/preview", response_model=schemas_email.EmailTemplatePreviewOut)
def preview(
    template_key: str,
    payload: schemas_email.EmailTemplatePreviewIn,
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
    db: Session = Depends(get_db),
):
    try:
        result = preview_template(
            db,
            template_key=template_key,
            variables=payload.variables,
            subject_override=payload.subject,
            html_body_override=payload.html_body,
            preheader_override=payload.preheader,
            force_dark=payload.force_dark,
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="テンプレートが見つかりません")
    return schemas_email.EmailTemplatePreviewOut(**result)


@router.post("/templates/{template_key}/test-send", status_code=status.HTTP_200_OK)
def test_send(
    template_key: str,
    payload: schemas_email.EmailTestSendIn,
    ctx: AdminContext = Depends(_require_perm("admin.email.write")),
    db: Session = Depends(get_db),
):
    rl = check_rate_limit(str(ctx.user.id), limit_key="test_send_admin")
    if not rl.allowed:
        raise HTTPException(
            status_code=429,
            detail=f"テスト送信の上限に達しました。{int(rl.retry_after_seconds)}秒後に再試行してください。",
        )
    sample = sample_variables_for_template(template_key)
    variables = {**sample, **payload.variables}
    result = send_templated_email(
        db,
        template_key=template_key,
        to_email=payload.to_email,
        variables=variables,
        is_test=True,
        force=False,
        sent_by_user_id=ctx.user.id,
        fallback_subject="テスト送信",
        fallback_html="<p>{{bodyTitle}}</p><p>{{bodyDescription}}</p>",
        raw_variable_keys={
            "shippingInfoBlock", "orderSummaryBlock", "itemsTable", "buttonsBlock",
            "notesBlock", "contactBlock", "signatureBlock",
            "kycInfoBlock", "buybackInfoBlock", "assessmentDetail", "memberInfoBlock",
        },
    )
    safe_commit(db)
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.error or "送信に失敗しました")
    return {"message": "テストメールを送信しました"}


@router.get("/send-logs", response_model=list[schemas_email.EmailSendLogOut])
def send_logs(
    status_filter: Optional[str] = Query(None, alias="status"),
    template_key: Optional[str] = Query(None),
    campaign_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
    db: Session = Depends(get_db),
):
    q = db.query(models_email.EmailSendLog).order_by(models_email.EmailSendLog.created_at.desc())
    if status_filter:
        q = q.filter(models_email.EmailSendLog.status == status_filter)
    if template_key:
        q = q.filter(models_email.EmailSendLog.template_key == template_key)
    if campaign_id:
        q = q.filter(models_email.EmailSendLog.campaign_id == campaign_id)
    return q.limit(limit).all()


@router.get("/campaigns", response_model=list[schemas_email.EmailCampaignOut])
def list_campaigns(
    limit: int = Query(50, ge=1, le=200),
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
    db: Session = Depends(get_db),
):
    return (
        db.query(models_email.EmailCampaign)
        .order_by(models_email.EmailCampaign.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/campaigns/{campaign_id}", response_model=schemas_email.EmailCampaignDetailOut)
def get_campaign(
    campaign_id: int,
    ctx: AdminContext = Depends(_require_perm("admin.email.read")),
    db: Session = Depends(get_db),
):
    campaign = db.query(models_email.EmailCampaign).filter(models_email.EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="キャンペーンが見つかりません")
    logs = (
        db.query(models_email.EmailSendLog)
        .filter(models_email.EmailSendLog.campaign_id == campaign_id)
        .order_by(models_email.EmailSendLog.created_at.desc())
        .limit(100)
        .all()
    )
    return schemas_email.EmailCampaignDetailOut(
        **schemas_email.EmailCampaignOut.model_validate(campaign).model_dump(),
        send_logs=[schemas_email.EmailSendLogOut.model_validate(log) for log in logs],
    )


@router.post("/campaigns/{campaign_id}/retry-failed")
def retry_campaign_failed(
    campaign_id: int,
    ctx: AdminContext = Depends(_require_perm("admin.email.write")),
    db: Session = Depends(get_db),
):
    campaign = db.query(models_email.EmailCampaign).filter(models_email.EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="キャンペーンが見つかりません")
    count = retry_failed_sends(db, campaign_id=campaign_id)
    safe_commit(db)
    return {"message": f"{count}件の再送を試行しました", "retried": count}


@router.post("/retry-failed")
def retry_all_failed(
    ctx: AdminContext = Depends(_require_perm("admin.email.write")),
    db: Session = Depends(get_db),
):
    count = retry_failed_sends(db)
    safe_commit(db)
    return {"message": f"{count}件の再送を試行しました", "retried": count}
