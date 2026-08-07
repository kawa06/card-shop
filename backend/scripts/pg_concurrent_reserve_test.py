"""PostgreSQL concurrent point reserve verification for Phase 3-4."""
from __future__ import annotations
import sys, threading, uuid
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
sys.path.insert(0, ".")
from config import settings
from database import Base
import models
import models_points  # noqa: F401
from auth import hash_password
from services.point_ledger import admin_grant_points, get_or_create_account, reserve_points_for_order
from services.admin_auth import bootstrap_admin_user

def order(session, user_id, total=1000):
    o = models.Order(user_id=user_id, total_amount=float(total), items_subtotal=float(total), shipping_fee=0, discount_amount=0, payment_method="stripe_card", payment_status="pending", status=models.OrderStatus.pending)
    session.add(o); session.flush(); return o

def main():
    url = settings.DATABASE_URL or ""
    if not url.lower().startswith("postgresql"):
        print("FAIL: need PostgreSQL"); return 1
    suffix = uuid.uuid4().hex[:10]
    test_email = f"pg-conc-{suffix}@phase34.invalid"
    admin_email = f"pg-conc-admin-{suffix}@phase34.invalid"
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session(); user_id = admin_id = None; order_ids = []
    try:
        user = models.User(email=test_email, name="PG test", password_hash=hash_password("x"), is_verified=True)
        db.add(user); db.commit(); db.refresh(user); user_id = user.id
        admin_user = models.User(email=admin_email, name="Admin", password_hash=hash_password("x"), is_admin=True, is_verified=True)
        db.add(admin_user); db.commit(); db.refresh(admin_user)
        admin = bootstrap_admin_user(db, admin_user); db.commit(); admin_id = admin.id
        admin_grant_points(db, user_id=user_id, amount=1000, reason="seed", admin_user_id=admin_id, idempotency_key=f"seed-{suffix}")
        db.commit()
        oa, ob = order(db, user_id), order(db, user_id); db.commit(); order_ids = [oa.id, ob.id]
        WS = sessionmaker(bind=engine); barrier = threading.Barrier(2)
        results = {"success": 0, "fail": 0}; codes = []; lock = threading.Lock()
        def worker(oid):
            s = WS()
            try:
                barrier.wait(timeout=5)
                try:
                    reserve_points_for_order(s, user_id=user_id, order_id=oid, amount=700); s.commit()
                    with lock: results["success"] += 1
                except HTTPException as e:
                    s.rollback(); 
                    with lock: results["fail"] += 1; codes.append(e.status_code)
            finally: s.close()
        t1 = threading.Thread(target=worker, args=(oa.id,)); t2 = threading.Thread(target=worker, args=(ob.id,))
        t1.start(); t2.start(); t1.join(15); t2.join(15)
        acct = get_or_create_account(db, user_id)
        print("success", results["success"], "fail", results["fail"], "codes", codes, "avail", acct.available_points, "reserved", acct.reserved_points)
        ok = results["success"]==1 and results["fail"]==1 and 400 in codes and acct.reserved_points==700 and acct.available_points>=0
        print("PASS" if ok else "FAIL"); return 0 if ok else 1
    finally:
        try:
            if user_id:
                db.query(models_points.PointTransaction).filter_by(user_id=user_id).delete(synchronize_session=False)
                db.query(models_points.PointAccount).filter_by(user_id=user_id).delete(synchronize_session=False)
                for oid in order_ids: db.query(models.Order).filter_by(id=oid).delete(synchronize_session=False)
                db.query(models.User).filter_by(id=user_id).delete(synchronize_session=False)
            if admin_id:
                db.query(models.AdminUser).filter_by(id=admin_id).delete(synchronize_session=False)
                db.query(models.User).filter(models.User.email==admin_email).delete(synchronize_session=False)
            db.commit()
        except Exception: db.rollback()
        db.close()
if __name__ == "__main__": raise SystemExit(main())
