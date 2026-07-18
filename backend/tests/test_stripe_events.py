from services.stripe_events import claim_stripe_event, save_stripe_payment_refs
import models


def test_claim_stripe_event_idempotent(db):
    assert claim_stripe_event(db, "evt_test_123", event_type="checkout.session.completed", order_id=1) is True
    db.commit()
    assert claim_stripe_event(db, "evt_test_123", event_type="checkout.session.completed", order_id=1) is False


def test_claim_stripe_event_empty_id_always_processes(db):
    assert claim_stripe_event(db, "") is True
    assert claim_stripe_event(db, "") is True


def test_save_stripe_payment_refs(db, paid_order):
    save_stripe_payment_refs(
        paid_order,
        payment_intent_id="pi_test_abc",
        event_id="evt_test_abc",
    )
    assert paid_order.stripe_payment_intent_id == "pi_test_abc"
    assert paid_order.stripe_event_id == "evt_test_abc"
