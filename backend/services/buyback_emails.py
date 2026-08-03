"""Transactional emails for buyback requests (Phase 5)."""

from __future__ import annotations

import html
import logging
from datetime import datetime

from sqlalchemy.orm import Session

import models
import models_buyback
from config import settings
from services.email_delivery import send_templated_email
from services.buyback_request_status import STATUS_DESCRIPTIONS, STATUS_LABELS
from services.verification import email_configured

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


_RAW_BUYBACK_KEYS = {"content", "itemsTable", "assessmentDetail"}


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

    variables = _buyback_template_variables(
        user, request, body_html=customer_body, extra={"itemsTable": _items_table_html(request)}
    )
    result = send_templated_email(
        db,
        template_key="buyback_request_submitted",
        to_email=user.email,
        variables=variables,
        fallback_subject=customer_subject,
        fallback_html=customer_html,
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


def notify_guardian_consent_requested(
    db: Session,
    consent: models_buyback.GuardianConsent,
    user: models.User,
    raw_token: str,
) -> None:
    link = f"{BUYLIST_BASE}/guardian-consent.html?token={raw_token}"
    body = f"""
      <p>{consent.guardian_name} 様</p>
      <p>{user.name or 'お子様'} 様のオンライン買取利用について、保護者同意が必要です。</p>
      <p>以下のリンクから同意内容をご確認のうえ、同意手続きを完了してください。</p>
      <p><a href="{link}">保護者同意ページを開く</a></p>
      <p style="font-size:12px;color:#666;">リンクの有効期限があります。心当たりがない場合は破棄してください。</p>
    """
    subject = "【KRX TCG】保護者同意のお願い"
    html_wrapped = _wrap_email(body)

    if not email_configured():
        if settings.DEBUG:
            logger.info("[GUARDIAN EMAIL MOCK] to=%s link=%s", consent.guardian_email, link)
        return

    send_templated_email(
        db,
        template_key="member_email_verify",
        to_email=consent.guardian_email,
        variables={"name": consent.guardian_name or "保護者", "content": body, "url": link},
        fallback_subject=subject,
        fallback_html=html_wrapped,
        raw_variable_keys={"content"},
    )


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
) -> tuple[bool, str | None]:
    ref_id = reference_id or str(request.id)
    if notification_already_sent(db, template_key, ref_id, reference_type=reference_type) and not force:
        return True, None

    html_wrapped = _wrap_email(body_html)
    if not email_configured():
        if settings.DEBUG:
            logger.info("[BUYBACK EMAIL MOCK] to=%s subject=%s key=%s", user.email, subject, template_key)
            _record_delivery(
                db,
                user_id=user.id,
                template_key=template_key,
                reference_id=ref_id,
                ok=True,
                reference_type=reference_type,
            )
        return True, None

    variables = _buyback_template_variables(user, request, body_html=body_html)
    result = send_templated_email(
        db,
        template_key=template_key,
        to_email=user.email,
        variables=variables,
        fallback_subject=subject,
        fallback_html=html_wrapped,
        reference_type=reference_type,
        reference_id=ref_id,
        raw_variable_keys=_RAW_BUYBACK_KEYS,
    )
    ok, err = result.ok, result.error
    _record_delivery(
        db,
        user_id=user.id,
        template_key=template_key,
        reference_id=ref_id,
        ok=ok,
        error=err,
        reference_type=reference_type,
    )
    return ok, err


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
    return _send_customer_template(
        db,
        user=user,
        request=request,
        template_key="buyback_assessment_ready",
        subject=subject,
        body_html=body,
        force=force,
    )


def notify_buyback_decision(
    db: Session,
    request: models_buyback.BuybackRequest,
    user: models.User,
    *,
    force: bool = False,
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
    return _send_customer_template(
        db,
        user=user,
        request=request,
        template_key=template_key,
        subject=subject,
        body_html=body,
        force=force,
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
    return _send_customer_template(
        db,
        user=user,
        request=request,
        template_key="buyback_package_shipped",
        subject=subject,
        body_html=body,
        force=force,
        reference_type="buyback_request",
        reference_id=f"{request.id}:pkg:{package.id}",
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
    link = _request_link(request.id)
    payout_amount = request.payout_total or request.assessed_total or request.estimated_total

    customer_body = f"""
      <p>{user.name or 'お客'} 様</p>
      <p>買取代金の振込が完了しました。</p>
      <ul>
        <li>申込番号：{request_number}</li>
        <li>振込金額：{_format_jpy(payout_amount)}</li>
        <li>振込日時：{request.paid_at.strftime('%Y/%m/%d %H:%M') if request.paid_at else '—'}</li>
      </ul>
      <p>金融機関の反映までお時間をいただく場合があります。</p>
      <p><a href="{link}">申込詳細を確認</a></p>
    """
    customer_html = _wrap_email(customer_body)
    customer_subject = f"【KRX TCG】買取代金の振込が完了しました（{request_number}）"

    if not email_configured():
        if settings.DEBUG:
            logger.info("[BUYBACK EMAIL MOCK] to=%s subject=%s", user.email, customer_subject)
            _record_delivery(
                db,
                user_id=user.id,
                template_key="buyback_payout_completed",
                reference_id=str(request.id),
                ok=True,
            )
        return True, None

    variables = _buyback_template_variables(user, request, body_html=customer_body)
    result = send_templated_email(
        db,
        template_key="buyback_payout_completed",
        to_email=user.email,
        variables=variables,
        fallback_subject=customer_subject,
        fallback_html=customer_html,
        reference_type="buyback_request",
        reference_id=str(request.id),
        raw_variable_keys=_RAW_BUYBACK_KEYS,
    )
    ok, err = result.ok, result.error
    _record_delivery(
        db,
        user_id=user.id,
        template_key="buyback_payout_completed",
        reference_id=str(request.id),
        ok=ok,
        error=err,
    )
    return ok, err


def notify_buyback_status_changed(
    db: Session,
    request: models_buyback.BuybackRequest,
    user: models.User,
    *,
    previous_status: str | None = None,
) -> tuple[bool, str | None]:
    """Generic customer email when request status changes."""
    request_number = request.request_number or str(request.id)
    status_label = STATUS_LABELS.get(request.status, request.status)
    desc = STATUS_DESCRIPTIONS.get(request.status, "")
    link = _request_link(request.id)
    note_html = ""
    if request.customer_status_note:
        note_html = f"<p>{html.escape(request.customer_status_note)}</p>"
    body = f"""
      <p>{html.escape(user.name or 'お客')} 様</p>
      <p>買取申請のステータスが更新されました。</p>
      <ul>
        {_public_codes(request)}
        <li>ステータス：{html.escape(status_label)}</li>
        {f'<li>{html.escape(desc)}</li>' if desc else ''}
      </ul>
      {note_html}
      <p><a href="{link}">申請詳細を確認</a></p>
    """
    subject = f"【KRX TCG】買取申請ステータス更新（{request_number}）"
    return _send_customer_template(
        db,
        user=user,
        template_key="buyback_status_changed",
        variables={
            "name": user.name or "お客",
            "buyNo": request_number,
            "statusLabel": status_label,
            "content": body,
        },
        fallback_subject=subject,
        fallback_html=body,
        reference_type="buyback_request",
        reference_id=str(request.id),
    )
