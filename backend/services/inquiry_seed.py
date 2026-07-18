"""Seed inquiry templates and default settings."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

import models
from services.inquiry_constants import DEFAULT_AUTO_REPLY_BODY, INQUIRY_CATEGORIES


CUSTOMER_TEMPLATES = [
    {
        "name": "発送状況を確認したい",
        "category": "shipping",
        "body": "注文番号：{orderNumber}\n\n上記注文の発送状況を確認したく、ご連絡しました。\n現在の発送状況と、発送予定日をご確認いただけますでしょうか。\n\nよろしくお願いいたします。",
    },
    {
        "name": "追跡番号を確認したい",
        "category": "shipping",
        "body": "注文番号：{orderNumber}\n\n上記注文の追跡番号を確認したく、ご連絡しました。\nすでに発送済みの場合は、配送会社名と追跡番号をご案内ください。\n\nよろしくお願いいたします。",
    },
    {
        "name": "注文内容を確認したい",
        "category": "order_payment",
        "body": "注文番号：{orderNumber}\n\n上記注文の内容を確認したく、ご連絡しました。\n\nよろしくお願いいたします。",
    },
    {
        "name": "支払い状況を確認したい",
        "category": "order_payment",
        "body": "注文番号：{orderNumber}\n\n上記注文の支払い状況を確認したく、ご連絡しました。\n\nよろしくお願いいたします。",
    },
    {
        "name": "商品の状態について確認したい",
        "category": "product",
        "body": "注文番号：{orderNumber}\n\n商品の状態について確認したく、ご連絡しました。\n\nよろしくお願いいたします。",
    },
    {
        "name": "ポイントが反映されていない",
        "category": "points",
        "body": "注文番号：{orderNumber}\n\n上記注文に関するポイントが、マイページに反映されていないようです。\n付与状況をご確認いただけますでしょうか。\n\nよろしくお願いいたします。",
    },
    {
        "name": "登録情報を変更したい",
        "category": "account",
        "body": "登録情報の変更についてご連絡しました。\n\n変更内容：\n\nよろしくお願いいたします。",
    },
    {
        "name": "キャンセルについて確認したい",
        "category": "order_payment",
        "body": "注文番号：{orderNumber}\n\nキャンセルについて確認したく、ご連絡しました。\n\nよろしくお願いいたします。",
    },
    {
        "name": "返品・返金について",
        "category": "refund",
        "body": "注文番号：{orderNumber}\n\n返品・返金についてご連絡しました。\n\n内容：\n\nよろしくお願いいたします。",
    },
    {
        "name": "その他",
        "category": "other",
        "body": "お問い合わせ内容：\n\n",
    },
]

ADMIN_TEMPLATES = [
    {
        "name": "発送準備中",
        "category": "shipping",
        "body": "お問い合わせありがとうございます。\n\nご注文の商品は現在発送準備中です。\n発送が完了しましたら、登録メールアドレスへ発送完了メールをお送りします。\n\n今しばらくお待ちください。",
    },
    {
        "name": "発送済み",
        "category": "shipping",
        "body": "お問い合わせありがとうございます。\n\nご注文の商品はすでに発送済みです。\n\n配送会社：{shippingCarrier}\n追跡番号：{trackingNumber}\n発送日：{shippedAt}\n\n配送状況は配送会社の追跡ページからご確認ください。",
    },
    {
        "name": "注文確認",
        "category": "order_payment",
        "body": "お問い合わせありがとうございます。\n\n以下の注文内容を確認しました。\n\n注文番号：{orderNumber}\n注文日：{orderedAt}\n注文金額：{totalAmount}\n注文状況：{orderStatus}\n\nご不明な点がございましたら、この問い合わせへご返信ください。",
    },
    {
        "name": "入金確認済み",
        "category": "order_payment",
        "body": "お問い合わせありがとうございます。\n\nご注文のお支払いは正常に確認できています。\n現在、商品の発送準備を進めています。\n\n発送完了まで今しばらくお待ちください。",
    },
    {
        "name": "ポイント反映済み",
        "category": "points",
        "body": "お問い合わせありがとうございます。\n\nポイントの付与状況を確認し、現在は正常に反映されています。\n\n現在のポイント残高：{pointBalance}ポイント\n\nマイページを再読み込みしてご確認ください。",
    },
    {
        "name": "確認中",
        "category": "other",
        "body": "お問い合わせありがとうございます。\n\n現在、詳しい状況を確認しています。\n確認が完了次第、改めてこちらからご連絡します。\n\n今しばらくお待ちください。",
    },
    {
        "name": "対応できない場合",
        "category": "other",
        "body": "お問い合わせありがとうございます。\n\n確認いたしましたが、今回は以下の理由によりご希望に沿うことができません。\n\n理由：\n{reason}\n\n何卒ご理解いただきますようお願いいたします。",
    },
    {
        "name": "解決済み",
        "category": "other",
        "body": "お問い合わせいただいた件について、対応が完了しました。\n\nほかに問題がない場合は、この問い合わせを解決済みとして終了します。\n追加のご質問がある場合は、このままご返信ください。",
    },
]


def seed_inquiry_data(db: Session) -> None:
    if not db.query(models.InquirySettings).filter(models.InquirySettings.id == 1).first():
        db.add(
            models.InquirySettings(
                id=1,
                shop_id=1,
                auto_reply_body=DEFAULT_AUTO_REPLY_BODY,
                allowed_categories=json.dumps(INQUIRY_CATEGORIES, ensure_ascii=False),
            )
        )

    existing = db.query(models.InquiryTemplate).filter(models.InquiryTemplate.shop_id == 1).count()
    if existing > 0:
        db.commit()
        return

    sort = 0
    for tpl in CUSTOMER_TEMPLATES:
        sort += 1
        db.add(
            models.InquiryTemplate(
                shop_id=1,
                template_type="customer",
                category=tpl["category"],
                name=tpl["name"],
                body=tpl["body"],
                sort_order=sort,
            )
        )
    sort = 0
    for tpl in ADMIN_TEMPLATES:
        sort += 1
        db.add(
            models.InquiryTemplate(
                shop_id=1,
                template_type="admin",
                category=tpl["category"],
                name=tpl["name"],
                body=tpl["body"],
                sort_order=sort,
            )
        )
    db.commit()
