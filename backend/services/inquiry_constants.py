INQUIRY_CATEGORIES = [
    "product",
    "order_payment",
    "shipping",
    "refund",
    "account",
    "points",
    "buyback",
    "bug",
    "other",
]

INQUIRY_CATEGORY_LABELS = {
    "product": "商品について",
    "order_payment": "注文・支払いについて",
    "shipping": "発送・配送について",
    "refund": "返品・返金について",
    "account": "会員情報について",
    "points": "ポイントについて",
    "buyback": "買取について",
    "bug": "サイトの不具合",
    "other": "その他",
    # legacy slugs (existing records / old templates)
    "order": "注文・支払いについて",
    "payment": "注文・支払いについて",
}

INQUIRY_STATUSES = [
    "submitted",
    "waiting_admin",
    "waiting_customer",
    "in_progress",
    "resolved",
    "closed",
]

INQUIRY_STATUS_LABELS = {
    "submitted": "送信済み",
    "waiting_admin": "ショップ返信待ち",
    "waiting_customer": "購入者返信待ち",
    "in_progress": "対応中",
    "resolved": "解決済み",
    "closed": "終了",
}

DEFAULT_AUTO_REPLY_BODY = """お問い合わせありがとうございます。

問い合わせ番号：{inquiryNumber}

お問い合わせを受け付けました。
内容を確認後、順次ご返信いたします。

返信が届きましたら、登録メールアドレスとマイページへ通知します。"""
