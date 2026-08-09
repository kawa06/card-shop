"""Typed notification event emitters for shop domains."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

import models
from services.user_notifications import create_user_notification, fanout_to_all_users, safe_notify

logger = logging.getLogger(__name__)


def notify_order_received(db: Session, order: models.Order) -> None:
    if not order.user_id:
        return
    safe_notify(
        db,
        user_id=order.user_id,
        type="order_received",
        category="order",
        title="ご注文を受け付けました",
        body=f"注文 #{order.id} を受け付けました。",
        related_entity_type="order",
        related_entity_id=order.id,
        action_url=f"/orders",
        dedupe_key=f"order_received:{order.id}",
        send_email=False,  # purchase email already sent separately
    )


def notify_order_paid(db: Session, order: models.Order) -> None:
    if not order.user_id:
        return
    safe_notify(
        db,
        user_id=order.user_id,
        type="order_paid",
        category="order",
        title="お支払いを確認しました",
        body=f"注文 #{order.id} のお支払いが確認されました。",
        related_entity_type="order",
        related_entity_id=order.id,
        action_url="/orders",
        dedupe_key=f"order_paid:{order.id}",
        send_email=False,
    )


def notify_order_shipped(db: Session, order: models.Order) -> None:
    if not order.user_id:
        return
    safe_notify(
        db,
        user_id=order.user_id,
        type="order_shipped",
        category="shipping",
        title="商品を発送しました",
        body=f"注文 #{order.id} を発送しました。",
        related_entity_type="order",
        related_entity_id=order.id,
        action_url="/orders",
        dedupe_key=f"order_shipped:{order.id}",
        send_email=False,  # shipping email is manual admin action today
    )


def notify_order_delivered(db: Session, order: models.Order) -> None:
    if not order.user_id:
        return
    safe_notify(
        db,
        user_id=order.user_id,
        type="order_delivered",
        category="shipping",
        title="配達が完了しました",
        body=f"注文 #{order.id} の配達が完了しました。",
        related_entity_type="order",
        related_entity_id=order.id,
        action_url="/orders",
        dedupe_key=f"order_delivered:{order.id}",
        send_email=False,
    )


def notify_buyback_status(db: Session, request, *, status: str) -> None:
    user_id = getattr(request, "user_id", None)
    if not user_id:
        return
    labels = {
        "assessed": ("査定が完了しました", "査定結果をご確認ください。"),
        "awaiting_customer": ("査定結果の確認をお願いします", "査定結果をご確認のうえ、承認または拒否をお選びください。"),
        "accepted": ("買取が承認されました", "買取申請が承認されました。"),
        "rejected": ("買取結果のお知らせ", "買取申請は却下されました。"),
        "payout_pending": ("振込準備中です", "買取代金の振込準備を進めています。"),
        "paid": ("振込が完了しました", "買取代金の振込が完了しました。"),
        "completed": ("買取が完了しました", "買取手続きが完了しました。"),
    }
    if status not in labels:
        return
    title, body = labels[status]
    rid = getattr(request, "id", None)
    safe_notify(
        db,
        user_id=int(user_id),
        type=f"buyback_{status}",
        category="appraisal",
        title=title,
        body=body,
        related_entity_type="buyback_request",
        related_entity_id=rid,
        action_url="/mypage",
        dedupe_key=f"buyback:{rid}:{status}",
        send_email=False,  # buyback emails already sent
    )


def notify_live_offer_reviewed(db: Session, offer, *, status: str) -> None:
    user_id = getattr(offer, "user_id", None)
    if not user_id:
        return
    if status == "accepted":
        title, body = "希望額が承認されました", "ライブ希望額が承認されました。購入手続きへ進めます。"
    elif status == "rejected":
        title, body = "希望額が却下されました", "ライブ希望額は却下されました。"
    elif status == "held":
        title, body = "希望額が検討中です", "ライブ希望額は検討中です。"
    else:
        return
    oid = getattr(offer, "id", None)
    stream_id = getattr(offer, "stream_id", None)
    action = f"/live/{stream_id}" if stream_id else "/mypage"
    safe_notify(
        db,
        user_id=int(user_id),
        type=f"live_offer_{status}",
        category="live",
        title=title,
        body=body,
        related_entity_type="live_offer",
        related_entity_id=oid,
        action_url=action,
        dedupe_key=f"live_offer:{oid}:{status}",
        send_email=False,
    )


def notify_auction_won(db: Session, auction, *, winner_user_id: int) -> None:
    aid = getattr(auction, "id", None)
    stream_id = getattr(auction, "stream_id", None)
    action = f"/live/{stream_id}" if stream_id else "/mypage"
    amount = getattr(auction, "current_price", None) or getattr(auction, "winning_amount", None)
    body = "オークションに落札しました。"
    if amount is not None:
        body = f"オークションに落札しました（落札額 ¥{int(amount):,}）。"
    safe_notify(
        db,
        user_id=int(winner_user_id),
        type="auction_won",
        category="auction",
        title="オークション落札のお知らせ",
        body=body,
        related_entity_type="live_auction",
        related_entity_id=aid,
        action_url=action,
        dedupe_key=f"auction_won:{aid}",
        send_email=False,
    )


def notify_coupon_assigned(db: Session, *, user_id: int, coupon, assignment_id: int) -> None:
    code = getattr(coupon, "code", "")
    name = getattr(coupon, "name", code)
    # In-app only here: loyalty email helper requires LoyaltyEmailSnapshot and is
    # intentionally not auto-wired to avoid double-send when admin later enables it.
    create_user_notification(
        db,
        user_id=user_id,
        type="coupon_assigned",
        category="campaign",
        title="クーポンが配布されました",
        body=f"クーポン「{name}」（{code}）が利用可能になりました。",
        related_entity_type="coupon",
        related_entity_id=getattr(coupon, "id", None),
        action_url="/mypage/coupons",
        dedupe_key=f"coupon_assign:{assignment_id}",
        send_email=False,
    )


def notify_announcement_to_users(db: Session, announcement: models.Announcement) -> None:
    title = (getattr(announcement, "title_ja", None) or announcement.title or "お知らせ").strip()
    body = "新しいお知らせが公開されました。"
    aid = announcement.id
    try:
        fanout_to_all_users(
            db,
            type="announcement_published",
            title=title,
            body=body,
            category="campaign",
            action_url=f"/mypage/announcements/{aid}",
            related_entity_type="announcement",
            related_entity_id=aid,
            dedupe_prefix=f"announcement:{aid}",
        )
    except Exception:
        logger.exception("announcement fanout failed id=%s", aid)


def notify_admin_broadcast(
    db: Session,
    *,
    title: str,
    body: str,
    user_id: Optional[int] = None,
    action_url: Optional[str] = None,
    category: str = "campaign",
    type: str = "admin_broadcast",
) -> int:
    if user_id:
        row = create_user_notification(
            db,
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            category=category,
            action_url=action_url or "/mypage/notifications",
            dedupe_key=f"admin_broadcast:{user_id}:{title}:{body[:40]}",
        )
        return 1 if row else 0
    import time

    prefix = f"admin_broadcast:{int(time.time())}"
    return fanout_to_all_users(
        db,
        type=type,
        title=title,
        body=body,
        category=category,
        action_url=action_url or "/mypage/notifications",
        dedupe_prefix=prefix,
    )
