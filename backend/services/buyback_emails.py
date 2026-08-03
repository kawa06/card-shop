"""Transactional emails for buyback requests (Phase 5)."""

from __future__ import annotations

import html
import logging
from datetime import datetime

from sqlalchemy.orm import Session

import models
import models_buyback
from config import settings
from services.buyback_email_auto_send import should_auto_send
from services.buyback_email_registry import (
    get_buyback_email_event,
    resolve_buyback_template_key,
    resolve_status_change_event,
)
from services.buyback_email_variables import (
    RAW_BUYBACK_VARIABLE_KEYS,
    build_buyback_email_variables,
)
from services.buyback_request_status import STATUS_DESCRIPTIONS, STATUS_LABELS
from services.email_delivery import render_template_string, send_templated_email
from services.email_order_layout import BUYBACK_EMAIL_BODY_SKELETON
from services.verification import email_configured
from services.kyc_emails import (
    notify_guardian_consent_requested,
    notify_identity_approved,
    notify_identity_rejected,
    notify_identity_resubmit_requested,
)

logger = logging.getLogger(__name__)

BUYLIST_BASE = settings.BUYLIST_URL.rstrip("/")
ADMIN_EMAIL = settings.MAIL_REPLY_TO or "oripakawa@gmail.com"


def _format_jpy(amount: int | None) -> str:
    return f"¥{int(amount or 0):,}"


def _request_link(request_id: int) -> str:
    return f"{BUYLIST_BASE}/request.html?id={request_id}"


def _items_table_html(request: models_buyback.BuybackRequest) -> str:
    rows = []
    for item in request.items:
        line_total = item.listed_unit_price * item.quantity
        rows.append(
            "<tr>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;'>{item.product_name_snapshot}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;'>{item.condition_code}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right;'>{item.quantity}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right;'>{_format_jpy(line_total)}</td>"
            "</tr>"
        )
    return (
        "<table style='width:100%;border-collapse:collapse;font-size:14px;'>"
        "<thead><tr>"
        "<th style='text-align:left;padding:8px;border-bottom:2px solid #ddd;'>商品</th>"
        "<th style='text-align:left;padding:8px;border-bottom:2px solid #ddd;'>状態</th>"
        "<th style='text-align:right;padding:8px;border-bottom:2px solid #ddd;'>数量</th>"
        "<th style='text-align:right;padding:8px;border-bottom:2px solid #ddd;'>参考小計</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _assessment_detail_table_html(request: models_buyback.BuybackRequest) -> str:
    rows = []
    shipping_total = 0
    for item in request.items:
        assessed = item.assessed_unit_price if item.assessed_unit_price is not None else item.listed_unit_price
        line_total = (assessed or 0) * item.quantity
        reduction = ""
        if item.rejection_reason_text:
            reduction = html.escape(item.rejection_reason_text)
        elif item.rejection_reason_code:
            reduction = html.escape(item.rejection_reason_code)
        if item.return_shipping_cost:
            shipping_total += int(item.return_shipping_cost)
        rows.append(
            "<tr>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;'>{html.escape(item.product_name_snapshot)}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right;'>{_format_jpy(assessed)}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:center;'>{item.quantity}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right;'>{_format_jpy(line_total)}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;font-size:12px;color:#666;'>{reduction or '—'}</td>"
            "</tr>"
        )
    footer = ""
    assessed_total = request.assessed_total or 0
    payout_total = request.payout_total or assessed_total
    if shipping_total:
        footer += f"<tr><td colspan='4' style='padding:8px;text-align:right;color:#666;'>返送送料</td><td style='padding:8px;text-align:right;'>{_format_jpy(shipping_total)}</td></tr>"
    footer += f"<tr><td colspan='4' style='padding:8px;text-align:right;font-weight:bold;'>査定合計</td><td style='padding:8px;text-align:right;font-weight:bold;'>{_format_jpy(assessed_total)}</td></tr>"
    footer += f"<tr><td colspan='4' style='padding:8px;text-align:right;font-weight:bold;color:#ca8a04;'>お支払予定額</td><td style='padding:8px;text-align:right;font-weight:bold;color:#ca8a04;'>{_format_jpy(payout_total)}</td></tr>"
    return (
        "<table style='width:100%;border-collapse:collapse;font-size:14px;margin:12px 0;'>"
        "<thead><tr>"
        "<th style='text-align:left;padding:8px;border-bottom:2px solid #ddd;'>商品</th>"
        "<th style='text-align:right;padding:8px;border-bottom:2px solid #ddd;'>査定単価</th>"
        "<th style='text-align:center;padding:8px;border-bottom:2px solid #ddd;'>数量</th>"
        "<th style='text-align:right;padding:8px;border-bottom:2px solid #ddd;'>小計</th>"
        "<th style='text-align:left;padding:8px;border-bottom:2px solid #ddd;'>減額理由</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + footer
        + "</tbody></table>"
    )


def _buyback_template_variables(
    user: models.User,
    request: models_buyback.BuybackRequest,
    *,
    body_html: str,
    extra: dict | None = None,
) -> dict:
    variables = {
        "name": user.name or "お客",
        "email": user.email,
        "buyNo": request.request_number or str(request.id),
        "content": body_html,
        "assessedTotal": _format_jpy(request.assessed_total),
        "payoutTotal": _format_jpy(request.payout_total or request.assessed_total),
        "assessmentDetail": _assessment_detail_table_html(request),
    }
    if extra:
        variables.update(extra)
    return variables


_RAW_BUYBACK_KEYS = RAW_BUYBACK_VARIABLE_KEYS


def send_buyback_event_email(
    db: Session,
    request: models_buyback.BuybackRequest,
    user: models.User,
    event_key: str,
    *,
    force: bool = False,
    send_email: bool | None = None,
    reference_type: str = "buyback_request",
    reference_id: str | None = None,
    include_assessment_detail: bool = False,
    package_tracking: str | None = None,
    package_carrier: str | None = None,
    return_reason: str | None = None,
    fallback_subject: str | None = None,
    to_email: str | None = None,
) -> tuple[bool, str | None]:
    """Central buyback email dispatcher with dedupe, auto-send prefs, and templated fallback."""
    if not should_auto_send(db, event_key, explicit=send_email):
        return True, None

    event = get_buyback_email_event(event_key)
    template_key = resolve_buyback_template_key(event_key, request.buyback_method)
    ref_id = reference_id or str(request.id)
    if event and event.dedupe_reference_suffix and reference_id is None:
        ref_id = f"{request.id}{event.dedupe_reference_suffix}"

    if notification_already_sent(db, template_key, ref_id, reference_type=reference_type) and not force:
        return True, None

    recipient = to_email or user.email
    if not recipient:
        return False, "recipient_missing"

    include_detail = include_assessment_detail or event_key in {
        "buyback_assessment_ready",
        "buyback_assessment_result",
        "buyback_awaiting_approval",
    }
    variables = build_buyback_email_variables(
        db,
        user,
        request,
        event_key,
        include_assessment_detail=include_detail,
        package_tracking=package_tracking,
        package_carrier=package_carrier,
        return_reason=return_reason,
    )
    subject = fallback_subject or f"【{variables.get('shopName', 'KRX TCG')}】{event.description if event else event_key}（{variables.get('buyNo', '')}）"
    fallback_html = render_template_string(
        BUYBACK_EMAIL_BODY_SKELETON,
        variables,
        raw_keys=RAW_BUYBACK_VARIABLE_KEYS,
    )

    if not email_configured():
        if settings.DEBUG:
            logger.info("[BUYBACK EMAIL MOCK] to=%s event=%s", recipient, event_key)
            _record_delivery(
                db,
                user_id=user.id,
                template_key=template_key,
                reference_id=ref_id,
                ok=True,
                reference_type=reference_type,
            )
        return True, None

    result = send_templated_email(
        db,
        template_key=template_key,
        to_email=recipient,
        variables=variables,
        fallback_subject=subject,
        fallback_html=fallback_html,
        fallback_text=variables.get("_text_body"),
        reference_type=reference_type,
        reference_id=ref_id,
        raw_variable_keys=RAW_BUYBACK_VARIABLE_KEYS,
    )
    _record_delivery(
        db,
        user_id=user.id,
        template_key=template_key,
        reference_id=ref_id,
        ok=result.ok,
        error=result.error,
        reference_type=reference_type,
    )
    return result.ok, result.error


def send_buyback_status_change_email(
    db: Session,
    request: models_buyback.BuybackRequest,
    user: models.User,
    *,
    to_status: str,
    previous_status: str | None = None,
    send_email: bool | None = None,
    force: bool = False,
) -> tuple[bool, str | None]:
    event_key = resolve_status_change_event(
        to_status=to_status,
        buyback_method=request.buyback_method,
    )
    if not event_key:
        event_key = "buyback_request_updated"
    return send_buyback_event_email(
        db,
        request,
        user,
        event_key,
        send_email=send_email,
        force=force,
        reference_id=f"{request.id}:{to_status}" if force else None,
    )


def _wrap_email(inner_html: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#111;">
      <h2 style="color:#ca8a04;margin:0 0 16px;">KRX TCG オンライン買取</h2>
      {inner_html}
      <p style="font-size:11px;color:#999;margin-top:24px;">&copy; KRX TCG</p>
    </div>
    """


def _record_delivery(
    db: Session,
    *,
    user_id: int | None,
    template_key: str,
    reference_id: str,
    ok: bool,
    error: str | None = None,
    reference_type: str = "buyback_request",
) -> None:
    try:
        db.add(
            models_buyback.NotificationDelivery(
                user_id=user_id,
                channel="email",
                template_key=template_key,
                reference_type=reference_type,
                reference_id=reference_id,
                status="sent" if ok else "failed",
                error_message=error,
                sent_at=datetime.utcnow() if ok else None,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Failed to record notification delivery")


def notify_buyback_request_submitted(
    db: Session,
    request: models_buyback.BuybackRequest,
    user: models.User,
) -> None:
    """Send customer confirmation and admin alert (best-effort)."""
    request_number = request.request_number or str(request.id)
    link = _request_link(request.id)
    status_label = STATUS_LABELS.get(request.status, request.status)

    customer_body = f"""
      <p>{user.name or 'お客'} 様</p>
      <p>買取申請を受け付けました。</p>
      <ul>
        <li>申込番号：{request_number}</li>
        <li>ステータス：{status_label}</li>
        <li>参考合計：{_format_jpy(request.estimated_total)}</li>
      </ul>
      <p>申込内容（掲載価格ベース）：</p>
      {_items_table_html(request)}
      <p style="font-size:13px;color:#555;margin-top:16px;">
        ※正式な買取金額は商品到着・査定後に確定します。
      </p>
      <div style="background:#fff7ed;border:1px solid #fdba74;border-radius:8px;padding:12px 16px;margin:16px 0;font-size:13px;color:#9a3412;">
        <p style="margin:0 0 8px;font-weight:bold;">【発送時の重要なお知らせ】</p>
        <p style="margin:0;">商品の発送は、必ず送料元払いでお願いいたします。着払いで発送された荷物は受け取らず、そのまま返送します。返送にかかる送料は利用者の負担となります。</p>
      </div>
      <p>商品の発送準備ができましたら、同梱の申込番号を記載のうえ、<strong>送料元払い</strong>で発送してください。</p>
      <p><a href="{link}">申込詳細を確認</a></p>
    """
    customer_html = _wrap_email(customer_body)
    customer_subject = f"【KRX TCG】買取申請を受け付けました（{request_number}）"

    if not email_configured():
        if settings.DEBUG:
            logger.info("[BUYBACK EMAIL MOCK] to=%s subject=%s", user.email, customer_subject)
            _record_delivery(
                db,
                user_id=user.id,
                template_key="buyback_request_submitted",
                reference_id=str(request.id),
                ok=True,
            )
        return

    variables = build_buyback_email_variables(
        db, user, request, "buyback_request_submitted",
        include_assessment_detail=False,
    )
    variables["itemsTable"] = _items_table_html(request)
    result = send_templated_email(
        db,
        template_key="buyback_request_submitted",
        to_email=user.email,
        variables=variables,
        fallback_subject=customer_subject,
        fallback_html=render_template_string(
            BUYBACK_EMAIL_BODY_SKELETON, variables, raw_keys=RAW_BUYBACK_VARIABLE_KEYS
        ),
        fallback_text=variables.get("_text_body"),
        reference_type="buyback_request",
        reference_id=str(request.id),
        raw_variable_keys=_RAW_BUYBACK_KEYS,
    )
    ok, err = result.ok, result.error
    _record_delivery(
        db,
        user_id=user.id,
        template_key="buyback_request_submitted",
        reference_id=str(request.id),
        ok=ok,
        error=err,
    )

    admin_body = f"""
      <p>新しい買取申請が届きました。</p>
      <ul>
        <li>申込番号：{request_number}</li>
        <li>申込者：{user.name}（{user.email}）</li>
        <li>参考合計：{_format_jpy(request.estimated_total)}</li>
        <li>発送方法：{request.shipping_method or '—'}</li>
      </ul>
      {f'<p>備考：{request.customer_note}</p>' if request.customer_note else ''}
      {_items_table_html(request)}
    """
    admin_html = _wrap_email(admin_body)
    admin_subject = f"【KRX TCG 管理】新規買取申請 {request_number}"

    admin_result = send_templated_email(
        db,
        template_key="buyback_request_admin_alert",
        to_email=ADMIN_EMAIL,
        variables={
            "name": user.name or "お客",
            "email": user.email,
            "buyNo": request_number,
            "content": admin_body,
        },
        fallback_subject=admin_subject,
        fallback_html=admin_html,
        reference_type="buyback_request",
        reference_id=str(request.id),
        raw_variable_keys={"content"},
    )
    admin_ok, admin_err = admin_result.ok, admin_result.error
    _record_delivery(
        db,
        user_id=None,
        template_key="buyback_request_admin_alert",
        reference_id=str(request.id),
        ok=admin_ok,
        error=admin_err,
    )


def _identity_notification_request_stub(user_id: int) -> models_buyback.BuybackRequest:
    """Minimal stub so _send_customer_template can build variables."""
    stub = models_buyback.BuybackRequest(
        id=0,
        user_id=user_id,
        status=models_buyback.BuybackRequestStatus.draft.value,
    )
    stub.items = []
    return stub


def payout_email_already_sent(db: Session, request_id: int) -> bool:
    return notification_already_sent(db, "buyback_payout_completed", str(request_id))


def notification_already_sent(
    db: Session,
    template_key: str,
    reference_id: str,
    *,
    reference_type: str = "buyback_request",
) -> bool:
    row = (
        db.query(models_buyback.NotificationDelivery)
        .filter(
            models_buyback.NotificationDelivery.template_key == template_key,
            models_buyback.NotificationDelivery.reference_type == reference_type,
            models_buyback.NotificationDelivery.reference_id == str(reference_id),
            models_buyback.NotificationDelivery.status == "sent",
        )
        .first()
    )
    return row is not None


def _public_codes(request: models_buyback.BuybackRequest) -> str:
    parts = []
    if request.public_buyback_code:
        parts.append(f"買取番号：{request.public_buyback_code}")
    parts.append(f"申込番号：{request.request_number or request.id}")
    if request.inbound_mgmt_id:
        parts.append(f"荷物管理ID：{request.inbound_mgmt_id}")
    return "".join(f"<li>{p}</li>" for p in parts)


def _send_customer_template(
    db: Session,
    *,
    user: models.User,
    request: models_buyback.BuybackRequest,
    template_key: str,
    subject: str,
    body_html: str,
    force: bool = False,
    reference_type: str = "buyback_request",
    reference_id: str | None = None,
    send_email: bool | None = None,
    include_assessment_detail: bool = False,
) -> tuple[bool, str | None]:
    return send_buyback_event_email(
        db,
        request,
        user,
        template_key,
        force=force,
        send_email=send_email,
        reference_type=reference_type,
        reference_id=reference_id,
        include_assessment_detail=include_assessment_detail,
        fallback_subject=subject,
    )


def notify_buyback_inbound_received(
    db: Session,
    request: models_buyback.BuybackRequest,
    user: models.User,
    *,
    force: bool = False,
) -> tuple[bool, str | None]:
    """Notify customer that inbound package was received at the shop."""
    request_number = request.request_number or str(request.id)
    link = _request_link(request.id)
    body = f"""
      <p>{user.name or 'お客'} 様</p>
      <p>買取商品のお荷物を受け取りました。</p>
      <ul>
        {_public_codes(request)}
        <li>ステータス：{STATUS_LABELS.get(request.status, request.status)}</li>
      </ul>
      <p>これから状態確認・査定を進めます。査定結果はメールでもお知らせします。</p>
      <p><a href="{link}">申込詳細を確認</a></p>
    """
    subject = f"【KRX TCG】買取商品を受け取りました（{request_number}）"
    return _send_customer_template(
        db,
        user=user,
        request=request,
        template_key="buyback_inbound_received",
        subject=subject,
        body_html=body,
        force=force,
    )


def notify_buyback_assessment_ready(
    db: Session,
    request: models_buyback.BuybackRequest,
    user: models.User,
    *,
    force: bool = False,
    send_email: bool | None = None,
) -> tuple[bool, str | None]:
    """Notify customer that assessment is ready / awaiting confirmation."""
    request_number = request.request_number or str(request.id)
    link = _request_link(request.id)
    status_label = STATUS_LABELS.get(request.status, request.status)
    body = f"""
      <p>{user.name or 'お客'} 様</p>
      <p>買取商品の査定が完了しました。</p>
      <ul>
        {_public_codes(request)}
        <li>ステータス：{status_label}</li>
        <li>査定合計：{_format_jpy(request.assessed_total)}</li>
        <li>お支払予定額：{_format_jpy(request.payout_total or request.assessed_total)}</li>
      </ul>
      <p>査定詳細：</p>
      {_assessment_detail_table_html(request)}
      <p>内容をご確認のうえ、マイページからご対応ください。</p>
      <p><a href="{link}">査定結果を確認</a></p>
    """
    subject = f"【KRX TCG】査定結果のご案内（{request_number}）"
    return send_buyback_event_email(
        db,
        request,
        user,
        "buyback_assessment_ready",
        force=force,
        send_email=send_email,
        include_assessment_detail=True,
        fallback_subject=subject,
    )


def notify_buyback_decision(
    db: Session,
    request: models_buyback.BuybackRequest,
    user: models.User,
    *,
    force: bool = False,
    send_email: bool | None = None,
) -> tuple[bool, str | None]:
    """Notify customer of accept / reject decision."""
    request_number = request.request_number or str(request.id)
    link = _request_link(request.id)
    status = request.status
    status_label = STATUS_LABELS.get(status, status)
    if status == models_buyback.BuybackRequestStatus.accepted.value:
        template_key = "buyback_accepted"
        lead = "買取が成立しました。"
        subject = f"【KRX TCG】買取が成立しました（{request_number}）"
    elif status == models_buyback.BuybackRequestStatus.rejected.value:
        template_key = "buyback_rejected"
        lead = "今回は買取不可となりました。"
        subject = f"【KRX TCG】買取結果のご連絡（{request_number}）"
    else:
        return False, f"unsupported status: {status}"

    body = f"""
      <p>{user.name or 'お客'} 様</p>
      <p>{lead}</p>
      <ul>
        {_public_codes(request)}
        <li>ステータス：{status_label}</li>
        <li>査定合計：{_format_jpy(request.assessed_total)}</li>
      </ul>
      <p><a href="{link}">申込詳細を確認</a></p>
    """
    return send_buyback_event_email(
        db,
        request,
        user,
        template_key,
        force=force,
        send_email=send_email,
        fallback_subject=subject,
    )


def notify_buyback_package_shipped(
    db: Session,
    request: models_buyback.BuybackRequest,
    user: models.User,
    package: models_buyback.BuybackShipmentPackage,
    *,
    force: bool = False,
) -> tuple[bool, str | None]:
    """Notify customer that an outbound package was shipped."""
    request_number = request.request_number or str(request.id)
    link = _request_link(request.id)
    tracking = package.tracking_number or "—"
    body = f"""
      <p>{user.name or 'お客'} 様</p>
      <p>お荷物を発送しました。</p>
      <ul>
        {_public_codes(request)}
        <li>梱包ID：{package.package_code}</li>
        <li>箱：{package.box_index}/{package.total_boxes}</li>
        <li>配送方法：{package.shipping_method or '—'}</li>
        <li>追跡番号：{tracking}</li>
      </ul>
      <p><a href="{link}">申込詳細を確認</a></p>
    """
    subject = f"【KRX TCG】お荷物を発送しました（{request_number}）"
    return send_buyback_event_email(
        db,
        request,
        user,
        "buyback_return_shipped",
        force=force,
        reference_id=f"{request.id}:pkg:{package.id}",
        package_tracking=package.tracking_number,
        package_carrier=package.shipping_method,
        fallback_subject=subject,
    )


def notify_buyback_payout_completed(
    db: Session,
    request: models_buyback.BuybackRequest,
    user: models.User,
    *,
    force: bool = False,
) -> tuple[bool, str | None]:
    """Send payout completion email to customer (best-effort)."""
    if payout_email_already_sent(db, request.id) and not force:
        return True, None

    request_number = request.request_number or str(request.id)
    customer_subject = f"【KRX TCG】買取代金の振込が完了しました（{request_number}）"
    return send_buyback_event_email(
        db,
        request,
        user,
        "buyback_payout_completed",
        force=force,
        fallback_subject=customer_subject,
    )


def notify_buyback_status_changed(
    db: Session,
    request: models_buyback.BuybackRequest,
    user: models.User,
    *,
    previous_status: str | None = None,
    send_email: bool | None = None,
    force: bool = False,
) -> tuple[bool, str | None]:
    """Customer email when request status changes — uses registry mapping."""
    return send_buyback_status_change_email(
        db,
        request,
        user,
        to_status=request.status,
        previous_status=previous_status,
        send_email=send_email,
        force=force,
    )


def notify_store_appraisal_estimate(
    db: Session,
    request: models_buyback.BuybackRequest,
    estimated_minutes: int,
    message: str | None = None,
) -> tuple[bool, str | None]:
    user = db.query(models.User).filter(models.User.id == request.user_id).first()
    if not user:
        return False, "user_not_found"
    request_number = request.public_buyback_code or request.request_number or str(request.id)
    link = _request_link(request.id)
    custom = html.escape((message or "").strip()) if message else ""
    body = f"""
      <p>{html.escape(user.name or 'お客')} 様</p>
      <p>買取番号 {html.escape(request_number)} の査定完了まで、約{estimated_minutes}分かかる見込みです。</p>
      {f'<p>{custom}</p>' if custom else ''}
      <p><a href="{link}">申請詳細を確認</a></p>
    """
    subject = "【KRX TCG】店舗買取の査定時間について"
    return _send_customer_template(
        db,
        user=user,
        request=request,
        template_key="buyback_store_appraisal_estimate",
        subject=subject,
        body_html=body,
    )
