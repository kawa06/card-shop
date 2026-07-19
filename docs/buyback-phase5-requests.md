# Buyback Phase 5 — Request submission

## Scope

- Submit buyback application from cart (`buyback_requests` + `buyback_request_items`)
- Request number format: `KBB-YYYYMMDD-NNNN`
- Status starts at `submitted` with history row
- Confirmation email to customer + admin alert (Resend via `_send_html_email`)
- Delivery logged in `notification_deliveries`
- Buylist UI: cart submit form, `requests.html`, `request.html`, account recent list

## API

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/buyback/requests` | JWT | Submit cart as request |
| GET | `/api/buyback/requests` | JWT | List user's requests |
| GET | `/api/buyback/requests/{id}` | JWT | Request detail |

### POST body

```json
{
  "customer_note": "optional",
  "shipping_method": "yu_pack"
}
```

## DB

New table (additive): `buyback_request_number_sequences`

## Tests

```bash
cd backend && pytest tests/test_buyback_requests.py tests/test_buyback_emails.py tests/test_buyback_cart.py tests/test_buyback_auth.py tests/test_user_linking.py -q
```

## Not in Phase 5

- KYC / payout accounts
- Admin buyback dashboard
- Tracking number updates from customer
- Status transitions beyond `submitted`
