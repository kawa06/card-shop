INQUIRY_CATEGORIES = [
    "order",
    "payment",
    "shipping",
    "product",
    "points",
    "account",
    "bug",
    "buyback",
    "other",
]

INQUIRY_CATEGORY_LABELS = {
    "order": "注文について",
    "payment": "支払いについて",
    "shipping": "発送について",
    "product": "商品について",
    "points": "ポイントについて",
    "account": "会員情報について",
    "bug": "サイトの不具合について",
    "buyback": "買取について",
    "other": "その他",
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
