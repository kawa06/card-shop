from services.stripe_service import create_checkout_session

session = create_checkout_session(
    order_id=99999,
    customer_email="diag-service@example.com",
    line_items=[
        {
            "price_data": {
                "currency": "jpy",
                "product_data": {"name": "diag-service"},
                "unit_amount": 1500,
            },
            "quantity": 1,
        }
    ],
    checkout_type="bank_transfer",
)
print(f"SERVICE_BANK_SESSION=ok id={session.id} url={'yes' if session.url else 'no'}")
