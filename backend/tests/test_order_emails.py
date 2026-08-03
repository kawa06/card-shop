from unittest.mock import patch

from services.order_emails import send_purchase_confirmation_email, send_shipping_completion_email


@patch("services.order_emails.send_templated_email")
def test_send_purchase_confirmation_email_success(mock_send, db, paid_order):
    from services.email_delivery import SendResult

    mock_send.return_value = SendResult(ok=True, used_template=False)
    ok, err = send_purchase_confirmation_email(db, paid_order.id)
    assert ok is True
    assert err is None
    db.refresh(paid_order)
    assert paid_order.purchase_email_sent_at is not None
    assert paid_order.email_send_status == "purchase_ok"
    mock_send.assert_called_once()


@patch("services.order_emails.send_templated_email")
def test_send_purchase_confirmation_dedup(mock_send, db, paid_order):
    from services.email_delivery import SendResult

    mock_send.return_value = SendResult(ok=True)
    send_purchase_confirmation_email(db, paid_order.id)
    send_purchase_confirmation_email(db, paid_order.id)
    mock_send.assert_called_once()


@patch("services.shipping_emails.send_templated_email")
def test_send_shipping_email_requires_tracking_for_trackable_method(mock_send, db, paid_order):
    paid_order.tracking_number = None
    db.commit()

    ok, err = send_shipping_completion_email(db, paid_order.id)
    assert ok is False
    assert "追跡番号" in (err or "")
    mock_send.assert_not_called()


@patch("services.shipping_emails.send_templated_email")
def test_send_shipping_email_success(mock_send, db, paid_order):
    from services.email_delivery import SendResult

    mock_send.return_value = SendResult(ok=True)
    paid_order.tracking_number = "12345678901"
    paid_order.shipping_carrier = "日本郵便"
    db.commit()

    ok, err = send_shipping_completion_email(db, paid_order.id)
    assert ok is True
    assert err is None
    db.refresh(paid_order)
    assert paid_order.shipping_email_sent_at is not None
    assert paid_order.shipping_status == "shipped"
    assert paid_order.email_send_status == "shipping_ok"
    assert mock_send.call_args.kwargs["template_key"] == "shipping_shipped"
    variables = mock_send.call_args.kwargs["variables"]
    assert variables["trackingNo"] == "12345678901"
    assert "trackings.post.japanpost.jp" in variables["trackingUrl"]
    fallback = mock_send.call_args.kwargs["fallback_html"]
    assert "12345678901" in fallback


@patch("services.shipping_emails.send_templated_email")
def test_send_shipping_email_allows_teikei_without_tracking(mock_send, db, paid_order):
    from services.email_delivery import SendResult

    mock_send.return_value = SendResult(ok=True)
    paid_order.shipping_method = "teikei_post"
    paid_order.tracking_number = None
    db.commit()

    ok, err = send_shipping_completion_email(db, paid_order.id)
    assert ok is True
    mock_send.assert_called_once()
