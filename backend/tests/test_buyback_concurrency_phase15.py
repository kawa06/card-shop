from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
import models
import models_admin  # noqa: F401
import models_buyback
from services.buyback_receiving import receive_inbound_package
from services.buyback_shipping import SHIP_CHECK_ITEMS, confirm_shipment
from services.buyback_packages import complete_package

ALL_CHECKS = {item["code"]: True for item in SHIP_CHECK_ITEMS}


def _session_factory(tmp_path, name: str):
    engine = create_engine(
        f"sqlite:///{tmp_path / name}",
        connect_args={"check_same_thread": False, "timeout": 10},
        hide_parameters=True,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _users_and_request(Session, *, status: str):
    with Session() as db:
        admin = models.User(
            email="concurrency-admin@example.com",
            name="Concurrency Admin",
            password_hash="test",
            is_admin=True,
            is_verified=True,
        )
        customer = models.User(
            email="concurrency-customer@example.com",
            name="Concurrency Customer",
            password_hash="test",
            is_verified=True,
            postal_code="6500001",
            region="兵庫県",
            city="神戸市",
            address_line1="中央区1-1",
        )
        db.add_all([admin, customer])
        db.flush()
        request = models_buyback.BuybackRequest(
            user_id=customer.id,
            request_number=f"KBB-CONCURRENT-{status}",
            status=status,
            estimated_total=1000,
        )
        db.add(request)
        db.commit()
        return admin.id, customer.id, request.id


def _seed_inbound(Session):
    admin_id, _, request_id = _users_and_request(Session, status="submitted")
    with Session() as db:
        inbound = models_buyback.BuybackInboundShipment(
            request_id=request_id,
            inbound_mgmt_id="KRX-PKG-CONCURRENT",
            status=models_buyback.BuybackInboundShipmentStatus.arrived.value,
        )
        db.add(inbound)
        db.flush()
        barcode = models_buyback.BuybackBarcode(
            scan_token="R" * 43,
            barcode_type=models_buyback.BuybackBarcodeType.application_inbound.value,
            entity_type=models_buyback.BuybackBarcodeEntityType.inbound_shipment.value,
            entity_id=inbound.id,
            is_active=True,
        )
        db.add(barcode)
        db.commit()
        return admin_id, request_id, inbound.id, barcode.scan_token


def _seed_packages(Session, *, count: int):
    admin_id, customer_id, request_id = _users_and_request(Session, status="rejected")
    package_rows: list[tuple[int, str]] = []
    with Session() as db:
        for index in range(1, count + 1):
            package = models_buyback.BuybackShipmentPackage(
                request_id=request_id,
                package_code=f"PKG-CONCURRENT-{index}",
                package_kind="return",
                box_index=index,
                total_boxes=count,
                destination_user_id=customer_id,
                shipping_method="tracked",
                tracking_number=f"TRACK-CONCURRENT-{index}",
                status=models_buyback.BuybackShipmentPackageStatus.packed.value,
            )
            db.add(package)
            db.flush()
            token = f"S{index}" + "X" * 41
            db.add(
                models_buyback.BuybackBarcode(
                    scan_token=token,
                    barcode_type=models_buyback.BuybackBarcodeType.package_outbound.value,
                    entity_type=models_buyback.BuybackBarcodeEntityType.shipment_package.value,
                    entity_id=package.id,
                    is_active=True,
                )
            )
            package_rows.append((package.id, token))
        db.commit()
    return admin_id, request_id, package_rows


def _status_call(callable_):
    try:
        callable_()
        return 200
    except HTTPException as exc:
        return exc.status_code


def test_simultaneous_receive_creates_one_receipt_and_history(tmp_path):
    engine, Session = _session_factory(tmp_path, "receive.db")
    admin_id, request_id, inbound_id, token = _seed_inbound(Session)
    barrier = Barrier(2)

    def worker():
        with Session() as db:
            admin = db.get(models.User, admin_id)
            barrier.wait()
            return _status_call(
                lambda: receive_inbound_package(
                    db,
                    admin_user=admin,
                    inbound_shipment_id=inbound_id,
                    scanned_code=token,
                    actual_item_count=1,
                )
            )

    with patch(
        "services.buyback_receiving.notify_buyback_inbound_received",
        return_value=(True, None),
    ):
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: worker(), range(2)))

    assert sorted(statuses) == [200, 409]
    with Session() as db:
        assert db.query(models_buyback.BuybackPackageReceipt).count() == 1
        histories = db.query(models_buyback.BuybackStatusHistory).all()
        assert len(histories) == 1
        assert histories[0].to_status == "received"
        assert db.get(models_buyback.BuybackRequest, request_id).status == "received"
        assert db.get(models_buyback.BuybackInboundShipment, inbound_id).status == "received"
    engine.dispose()


def test_simultaneous_same_return_package_is_safe_and_not_500(tmp_path):
    engine, Session = _session_factory(tmp_path, "ship-same.db")
    admin_id, request_id, packages = _seed_packages(Session, count=1)
    package_id, token = packages[0]
    barrier = Barrier(2)

    def worker():
        with Session() as db:
            admin = db.get(models.User, admin_id)
            barrier.wait()
            return _status_call(
                lambda: confirm_shipment(
                    db,
                    admin_user=admin,
                    package_id=package_id,
                    checklist=ALL_CHECKS,
                    scanned_code=token,
                )
            )

    with patch(
        "services.buyback_shipping.notify_buyback_package_shipped",
        return_value=(True, None),
    ):
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: worker(), range(2)))

    assert sorted(statuses) == [200, 409]
    with Session() as db:
        assert db.query(models_buyback.BuybackShipmentConfirmation).count() == 1
        assert db.query(models_buyback.BuybackShipmentAddressSnapshot).count() == 1
        assert db.get(models_buyback.BuybackShipmentPackage, package_id).status == "shipped"
        assert db.get(models_buyback.BuybackRequest, request_id).status == "returned"
    engine.dispose()


def test_simultaneous_final_two_return_boxes_set_request_returned_once(tmp_path):
    engine, Session = _session_factory(tmp_path, "ship-multi.db")
    admin_id, request_id, packages = _seed_packages(Session, count=2)
    barrier = Barrier(2)

    def worker(package_data):
        package_id, token = package_data
        with Session() as db:
            admin = db.get(models.User, admin_id)
            barrier.wait()
            return _status_call(
                lambda: confirm_shipment(
                    db,
                    admin_user=admin,
                    package_id=package_id,
                    checklist=ALL_CHECKS,
                    scanned_code=token,
                )
            )

    with patch(
        "services.buyback_shipping.notify_buyback_package_shipped",
        return_value=(True, None),
    ):
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(worker, packages))

    assert statuses == [200, 200]
    with Session() as db:
        assert db.query(models_buyback.BuybackShipmentConfirmation).count() == 2
        assert db.query(models_buyback.BuybackShipmentAddressSnapshot).count() == 2
        assert db.get(models_buyback.BuybackRequest, request_id).status == "returned"
        returned_history = (
            db.query(models_buyback.BuybackStatusHistory)
            .filter(models_buyback.BuybackStatusHistory.to_status == "returned")
            .all()
        )
        assert len(returned_history) == 1
    engine.dispose()


def test_stale_package_completion_cannot_regress_shipped_state(tmp_path):
    engine, Session = _session_factory(tmp_path, "complete-versus-ship.db")
    admin_id, _, packages = _seed_packages(Session, count=1)
    package_id, token = packages[0]

    with Session() as stale_db:
        admin = stale_db.get(models.User, admin_id)
        stale_package = stale_db.get(
            models_buyback.BuybackShipmentPackage, package_id
        )
        assert stale_package.status == "packed"

        with Session() as shipping_db:
            shipping_admin = shipping_db.get(models.User, admin_id)
            with patch(
                "services.buyback_shipping.notify_buyback_package_shipped",
                return_value=(True, None),
            ):
                confirm_shipment(
                    shipping_db,
                    admin_user=shipping_admin,
                    package_id=package_id,
                    checklist=ALL_CHECKS,
                    scanned_code=token,
                )

        with pytest.raises(HTTPException) as exc_info:
            complete_package(
                stale_db,
                admin_user=admin,
                package_id=package_id,
            )
        assert exc_info.value.status_code == 409

    with Session() as db:
        package = db.get(models_buyback.BuybackShipmentPackage, package_id)
        assert package.status == "shipped"
        assert (
            db.query(models_buyback.BuybackShipmentConfirmation)
            .filter(
                models_buyback.BuybackShipmentConfirmation.package_id
                == package_id
            )
            .count()
            == 1
        )
    engine.dispose()


def test_receive_rolls_back_when_success_audit_fails(tmp_path):
    engine, Session = _session_factory(tmp_path, "rollback.db")
    admin_id, request_id, inbound_id, token = _seed_inbound(Session)
    with Session() as db:
        admin = db.get(models.User, admin_id)
        with patch(
            "services.buyback_receiving._log_scan",
            side_effect=RuntimeError("audit unavailable"),
        ):
            try:
                receive_inbound_package(
                    db,
                    admin_user=admin,
                    inbound_shipment_id=inbound_id,
                    scanned_code=token,
                )
            except RuntimeError:
                db.rollback()

    with Session() as db:
        assert db.query(models_buyback.BuybackPackageReceipt).count() == 0
        assert db.query(models_buyback.BuybackStatusHistory).count() == 0
        assert db.get(models_buyback.BuybackRequest, request_id).status == "submitted"
        assert db.get(models_buyback.BuybackInboundShipment, inbound_id).status == "arrived"
    engine.dispose()


def test_ship_rolls_back_when_success_audit_fails(tmp_path):
    engine, Session = _session_factory(tmp_path, "ship-rollback.db")
    admin_id, request_id, packages = _seed_packages(Session, count=1)
    package_id, token = packages[0]
    with Session() as db:
        admin = db.get(models.User, admin_id)
        with patch(
            "services.buyback_shipping._log_scan",
            side_effect=RuntimeError("audit unavailable"),
        ):
            try:
                confirm_shipment(
                    db,
                    admin_user=admin,
                    package_id=package_id,
                    checklist=ALL_CHECKS,
                    scanned_code=token,
                )
            except RuntimeError:
                db.rollback()

    with Session() as db:
        assert db.query(models_buyback.BuybackShipmentConfirmation).count() == 0
        assert db.query(models_buyback.BuybackShipmentAddressSnapshot).count() == 0
        assert db.get(models_buyback.BuybackShipmentPackage, package_id).status == "packed"
        assert db.get(models_buyback.BuybackRequest, request_id).status == "rejected"
    engine.dispose()
