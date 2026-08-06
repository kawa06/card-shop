from __future__ import annotations
import json, os, re, sys, time
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ENV = ROOT / "frontend" / ".env.local"
OUT_DIR = ROOT / "artifacts" / "phase1-screenshots"
BASE_URL = os.getenv("PHASE1_BASE_URL", "http://localhost:3000").rstrip("/")
ADMIN_EMAIL = os.getenv("PHASE1_ADMIN_EMAIL", "rikukai0609@icloud.com").strip().lower()

PAGES = [
    ("01-hub", "/admin/buyback/requests"),
    ("02-mail-list", "/admin/buyback/mail/requests"),
    ("03-store-list", "/admin/buyback/store/requests"),
]

PHASE2_PAGES = [
    ("01-dashboard-kpi", "/admin"),
    ("02-fulfillment", "/admin/fulfillment"),
    ("03-order-scan", "/admin/orders/scan"),
    ("04-notification-bell", "/admin"),
]

def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8-sig")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")

def get_sign_in_url(secret_key: str, email: str) -> str | None:
    headers = {"Authorization": f"Bearer {secret_key}"}
    users = httpx.get("https://api.clerk.com/v1/users", params={"email_address": [email]}, headers=headers, timeout=30.0)
    users.raise_for_status()
    data = users.json()
    if not data:
        return None
    token = httpx.post("https://api.clerk.com/v1/sign_in_tokens", json={"user_id": data[0]["id"]}, headers=headers, timeout=30.0)
    token.raise_for_status()
    return token.json().get("url")

def wait_admin_ready(page, timeout_ms: int = 120000) -> bool:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        url = page.url
        body = page.inner_text("body")
        if "/sign-in" in url:
            time.sleep(2)
            continue
        if any(token in body for token in ("買取管理", "商品査定", "郵送買取", "店舗買取", "申込一覧")):
            return True
        time.sleep(2)
    return False

def shot(page, name: str, report: dict) -> None:
    out = OUT_DIR / f"{name}.png"
    page.screenshot(path=str(out), full_page=True)
    body = page.inner_text("body")
    report["screenshots"].append({
        "file": str(out.relative_to(ROOT)),
        "url": page.url,
        "title": page.title(),
        "is_sign_in": "/sign-in" in page.url,
        "has_admin_ui": any(t in body for t in ("買取管理", "商品査定", "郵送買取", "店舗買取")),
    })

def wait_shop_admin_ready(page, timeout_ms: int = 120000) -> bool:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        url = page.url
        if "/sign-in" in url:
            time.sleep(2)
            continue
        body = page.inner_text("body")
        if any(
            token in body
            for token in (
                "管理ダッシュボード",
                "管理画面",
                "発送管理",
                "注文スキャン",
                "注文管理",
                "買取申請管理",
            )
        ):
            return True
        time.sleep(2)
    return False

def clerk_sign_in(page, secret_key: str, report: dict) -> None:
    sign_in_url = get_sign_in_url(secret_key, ADMIN_EMAIL)
    if not sign_in_url:
        report["notes"].append("Clerk admin user not found")
        return
    page.goto(sign_in_url, wait_until="networkidle", timeout=180000)
    time.sleep(5)
    for _ in range(90):
        url = page.url
        if "clerk" not in url.lower() and "/sign-in" not in url:
            break
        time.sleep(2)
    page.goto(f"{BASE_URL}/auth/after-sign-in", wait_until="networkidle", timeout=180000)
    for _ in range(60):
        if "/admin" in page.url and wait_shop_admin_ready(page, 5000):
            report["after_sign_in_url"] = page.url
            report["admin_signed_in"] = True
            return
        if wait_shop_admin_ready(page, 3000):
            report["after_sign_in_url"] = page.url
            report["admin_signed_in"] = True
            return
        page.goto(f"{BASE_URL}/admin", wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)
    report["after_sign_in_url"] = page.url
    report["admin_signed_in"] = wait_shop_admin_ready(page, 10000)

def first_detail_href(page, list_path: str) -> str | None:
    page.goto(BASE_URL + list_path, wait_until="domcontentloaded", timeout=120000)
    if not wait_admin_ready(page, 60000):
        return None
    link = page.locator("a[href*='/requests/']").first
    if link.count() == 0:
        return None
    return link.get_attribute("href")

def capture_detail(page, prefix: str, path: str, report: dict) -> None:
    page.goto(BASE_URL + path, wait_until="domcontentloaded", timeout=120000)
    if not wait_admin_ready(page, 90000):
        report["notes"].append(f"{prefix} detail not ready")
        return
    shot(page, f"{prefix}-detail", report)
    body = page.inner_text("body")
    report.setdefault("detail_checks", {})[prefix] = {
        "has_assessment_table": "商品査定" in body,
        "has_buy_buttons": ("買取する" in body and "買取しない" in body),
        "has_present": "査定結果を提示" in body,
        "has_history": "査定履歴" in body,
        "has_store_workflow": "店舗" in body and ("ワークフロー" in body or "来店" in body or "チェックイン" in body),
    }
    try:
        page.get_by_role("button", name="減額").first.click(timeout=5000)
        time.sleep(1)
        shot(page, f"{prefix}-reduced", report)
    except Exception as exc:
        report.setdefault("interaction_errors", {})[f"{prefix}-reduced"] = str(exc)
    try:
        select = page.locator("table select").first
        if select.count() > 0:
            options = select.locator("option")
            if options.count() > 1:
                value = options.nth(1).get_attribute("value")
                if value:
                    select.select_option(value)
                    time.sleep(1)
                    shot(page, f"{prefix}-condition", report)
    except Exception as exc:
        report.setdefault("interaction_errors", {})[f"{prefix}-condition"] = str(exc)
    try:
        textarea = page.locator("textarea").first
        if textarea.count() > 0:
            textarea.fill("Phase1 dev verification comment")
            time.sleep(1)
            shot(page, f"{prefix}-comment", report)
    except Exception as exc:
        report.setdefault("interaction_errors", {})[f"{prefix}-comment"] = str(exc)

def phase2_api_verify() -> dict:
    """Backend/API checks for Phase2 manual verification items."""
    import sys

    backend = ROOT / "backend"
    sys.path.insert(0, str(backend))
    prev_cwd = os.getcwd()
    os.chdir(backend)
    os.environ["ADMIN_PROXY_SECRET"] = "test-only-admin-proxy-secret"
    from datetime import datetime

    import models
    import models_buyback  # noqa: F401
    import models_admin  # noqa: F401
    from config import settings
    from fastapi.testclient import TestClient
    from main import app
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from database import Base, get_db
    from services.barcode_render import ensure_order_barcode, resolve_order_by_scan_code
    from services.admin_seed import seed_admin_rbac
    from tests.conftest import admin_headers, auth_headers, create_admin_user

    settings.DEBUG = True
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    seed_admin_rbac(session)
    user = create_admin_user(session, email="rikukai0609@icloud.com", role_code="owner")
    order = models.Order(
        user_id=user.id,
        total_amount=2000,
        payment_status="paid",
        paid_at=datetime.utcnow(),
        order_number="ORD-VERIFY-001",
        shipping_status="unshipped",
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    headers = admin_headers("rikukai0609@icloud.com")
    results: dict = {}

    b1 = ensure_order_barcode(session, order=order)
    session.commit()
    b2 = ensure_order_barcode(session, order=order)
    session.commit()
    dup_count = session.query(models.OrderBarcode).filter(models.OrderBarcode.order_id == order.id).count()
    results["duplicate_barcode"] = {
        "pass": b1.id == b2.id and b1.scan_token == b2.scan_token and dup_count == 1,
        "barcode_rows": dup_count,
        "token_stable": b1.scan_token == b2.scan_token,
    }

    scan1 = client.post("/api/admin/orders/scan", json={"code": b1.scan_token}, headers=headers)
    scan2 = client.post("/api/admin/orders/scan", json={"code": b1.scan_token}, headers=headers)
    results["double_scan"] = {
        "pass": scan1.status_code == 200 and scan2.status_code == 200,
        "same_order_id": scan1.json().get("order_id") == scan2.json().get("order_id"),
        "idempotent": scan1.json() == scan2.json(),
        "note": "注文スキャンは参照専用（副作用なし）のため同一結果返却で二重処理を防止",
    }

    resolved = resolve_order_by_scan_code(session, b1.scan_token)
    results["barcode_read"] = {
        "pass": resolved is not None and resolved.id == order.id,
        "order_number": resolved.order_number if resolved else None,
    }

    logs_before = client.get(f"/api/admin/orders/{order.id}/shipment-logs", headers=headers)
    ship = client.patch(
        f"/api/admin/orders/{order.id}/shipping",
        json={"shipping_status": "preparing"},
        headers=headers,
    )
    logs_after = client.get(f"/api/admin/orders/{order.id}/shipment-logs", headers=headers)
    results["shipment_log"] = {
        "pass": ship.status_code == 200 and len(logs_after.json()) >= len(logs_before.json()),
        "logs_count": len(logs_after.json()),
    }

    csv_res = client.get("/api/admin/buyback/requests/export.csv", headers=headers)
    csv_bytes = csv_res.content
    results["csv_utf8_bom"] = {
        "pass": csv_bytes[:3] == b"\xef\xbb\xbf",
        "status_code": csv_res.status_code,
        "bom_hex": csv_bytes[:3].hex() if len(csv_bytes) >= 3 else "",
    }

    app.dependency_overrides.clear()
    session.close()
    os.chdir(prev_cwd)
    return results


def phase2_main() -> int:
    load_dotenv(FRONTEND_ENV)
    secret_key = os.getenv("CLERK_SECRET_KEY", "").strip()
    from playwright.sync_api import sync_playwright

    out_dir = ROOT / "artifacts" / "phase2-manual-verify"
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "base_url": BASE_URL,
        "screenshots": [],
        "notes": [],
        "api_checks": {},
    }

    try:
        report["api_checks"] = phase2_api_verify()
    except Exception as exc:
        report["api_checks"] = {"error": str(exc)}

    def shot2(page, name: str, extra: dict | None = None) -> None:
        out = out_dir / f"{name}.png"
        page.screenshot(path=str(out), full_page=True)
        body = page.inner_text("body")
        entry = {
            "file": str(out.relative_to(ROOT)),
            "url": page.url,
            "title": page.title(),
            "is_sign_in": "/sign-in" in page.url,
            "has_admin_ui": wait_shop_admin_ready(page, 2000),
        }
        if extra:
            entry.update(extra)
        report["screenshots"].append(entry)

    with sync_playwright() as p:
        headed = os.getenv("PHASE2_HEADED", "").strip() in ("1", "true", "yes")
        browser = p.chromium.launch(headless=not headed, slow_mo=150 if headed else 0)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, locale="ja-JP")
        if secret_key:
            clerk_sign_in(page, secret_key, report)
        else:
            report["notes"].append("CLERK_SECRET_KEY missing")

        if not report.get("admin_signed_in"):
            report["notes"].append("Clerk sign-in failed; UI screenshots may show sign-in page")

        ui_routes = [
            ("01-dashboard-kpi", "/admin"),
            ("02-notification-bell", "/admin"),
            ("03-fulfillment", "/admin/fulfillment"),
            ("04-order-scan", "/admin/orders/scan"),
            ("08-buyback-list-csv", "/admin/buyback/requests"),
        ]
        for name, path in ui_routes:
            try:
                page.goto(BASE_URL + path, wait_until="networkidle", timeout=120000)
                time.sleep(2)
                shot2(page, name)
            except Exception as exc:
                report.setdefault("errors", {})[name] = str(exc)

        try:
            page.goto(BASE_URL + "/admin", wait_until="networkidle", timeout=120000)
            time.sleep(1)
            bell = page.locator('button[aria-label="通知"]')
            if bell.count() > 0:
                bell.first.click()
                time.sleep(1)
                shot2(page, "02-notification-bell-open")
        except Exception as exc:
            report.setdefault("errors", {})["notification-bell-open"] = str(exc)

        try:
            page.goto(BASE_URL + "/admin/buyback/requests", wait_until="networkidle", timeout=120000)
            csv_btn = page.get_by_role("button", name=re.compile("CSV"))
            if csv_btn.count() > 0:
                with page.expect_download(timeout=60000) as dl_info:
                    csv_btn.first.click()
                download = dl_info.value
                csv_path = out_dir / "buyback-export.csv"
                download.save_as(str(csv_path))
                raw = csv_path.read_bytes()
                report["csv_download"] = {
                    "file": str(csv_path.relative_to(ROOT)),
                    "has_bom": raw[:3] == b"\xef\xbb\xbf",
                    "size": len(raw),
                }
                shot2(page, "08-buyback-csv-clicked")
        except Exception as exc:
            report.setdefault("errors", {})["buyback-csv"] = str(exc)

        order_id: int | None = None
        try:
            page.goto(BASE_URL + "/admin/fulfillment", wait_until="networkidle", timeout=120000)
            detail = page.locator("a[href*='/admin/orders/']").first
            if detail.count() > 0:
                href = detail.get_attribute("href") or ""
                m = re.search(r"/admin/orders/(\d+)", href)
                if m:
                    order_id = int(m.group(1))
        except Exception as exc:
            report.setdefault("errors", {})["find-order"] = str(exc)

        if order_id is None:
            try:
                page.goto(BASE_URL + "/admin/orders", wait_until="networkidle", timeout=120000)
                link = page.locator("a[href*='/admin/orders/']").first
                if link.count() > 0:
                    href = link.get_attribute("href") or ""
                    m = re.search(r"/admin/orders/(\d+)", href)
                    if m:
                        order_id = int(m.group(1))
            except Exception as exc:
                report.setdefault("errors", {})["find-order-fallback"] = str(exc)

        report["order_id_used"] = order_id

        if order_id:
            try:
                page.goto(f"{BASE_URL}/admin/orders/{order_id}", wait_until="networkidle", timeout=120000)
                time.sleep(2)
                shot2(page, "05-order-detail")
            except Exception as exc:
                report.setdefault("errors", {})["order-detail"] = str(exc)
            try:
                page.goto(f"{BASE_URL}/admin/orders/{order_id}/print/shipping-label", wait_until="networkidle", timeout=120000)
                time.sleep(2)
                shot2(page, "06-shipping-label-barcode")
            except Exception as exc:
                report.setdefault("errors", {})["shipping-label"] = str(exc)
            try:
                page.goto(BASE_URL + "/admin/orders/scan", wait_until="networkidle", timeout=120000)
                time.sleep(1)
                input_box = page.locator('input[type="text"]').first
                if input_box.count() > 0:
                    input_box.fill(str(order_id))
                    input_box.press("Enter")
                    time.sleep(2)
                    shot2(page, "07-barcode-scan-result")
            except Exception as exc:
                report.setdefault("errors", {})["barcode-scan"] = str(exc)

        browser.close()

    (out_dir / "verify-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    admin_shots = sum(1 for s in report["screenshots"] if s.get("has_admin_ui"))
    print(json.dumps({
        "admin_signed_in": report.get("admin_signed_in"),
        "screenshot_count": len(report["screenshots"]),
        "admin_ui_shots": admin_shots,
        "api_checks": report.get("api_checks"),
        "order_id_used": report.get("order_id_used"),
        "output_dir": str(out_dir.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))
    api_ok = all(v.get("pass") for v in report.get("api_checks", {}).values() if isinstance(v, dict))
    return 0 if report.get("admin_signed_in") and admin_shots >= 5 and api_ok else 1


def main() -> int:
    load_dotenv(FRONTEND_ENV)
    secret_key = os.getenv("CLERK_SECRET_KEY", "").strip()
    from playwright.sync_api import sync_playwright
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "base_url": BASE_URL,
        "has_admin_proxy_secret": bool(os.getenv("ADMIN_PROXY_SECRET", "").strip()),
        "screenshots": [],
        "notes": [],
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, locale="ja-JP")
        if secret_key:
            clerk_sign_in(page, secret_key, report)
        else:
            report["notes"].append("CLERK_SECRET_KEY missing")
        for name, path in PAGES:
            try:
                page.goto(BASE_URL + path, wait_until="domcontentloaded", timeout=120000)
                wait_admin_ready(page, 90000)
                shot(page, name, report)
            except Exception as exc:
                report.setdefault("errors", {})[name] = str(exc)
        for prefix, list_path in [("04-mail", "/admin/buyback/mail/requests"), ("05-store", "/admin/buyback/store/requests")]:
            try:
                href = first_detail_href(page, list_path)
                if not href:
                    report["notes"].append(f"No detail link for {prefix}")
                    continue
                capture_detail(page, prefix, href, report)
            except Exception as exc:
                report.setdefault("errors", {})[prefix] = str(exc)
        browser.close()
    (OUT_DIR / "capture-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    safe = {k: v for k, v in report.items() if k != "screenshots"}
    safe["screenshot_count"] = len(report["screenshots"])
    safe["admin_ui_shots"] = sum(1 for s in report["screenshots"] if s.get("has_admin_ui"))
    safe["sign_in_only_shots"] = sum(1 for s in report["screenshots"] if s.get("is_sign_in"))
    safe["screenshot_files"] = [s["file"] for s in report["screenshots"]]
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0 if safe["admin_ui_shots"] > 0 else 1


def restore_phase2_frontend() -> None:
    """Write Phase 2 admin frontend pages as UTF-8 (Windows-safe)."""
    root = ROOT / "frontend"
    dash = "\u2014"
    labels = {
        "packing": "\u6761\u5305\u4e2d",
        "in_transit": "\u914d\u9001\u4e2d",
        "received": "\u53d7\u53d6\u6e08\u307f",
    }

    def w(rel: str, content: str) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")

    w(
        "components/admin/AdminNotificationBell.tsx",
        """'use client'

import { useEffect, useRef, useState } from 'react'
import { Bell } from 'lucide-react'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminNotificationsApi } from '@/lib/api'
import type { AdminInAppNotification } from '@/lib/types'

export function AdminNotificationBell() {
  const { hasPermission } = useAdminPermissions()
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<AdminInAppNotification[]>([])
  const panelRef = useRef<HTMLDivElement>(null)
  const canRead = hasPermission('admin.email.read')

  useEffect(() => {
    if (!canRead) return
    void adminNotificationsApi.getUnreadCount().then((res) => setUnread(res.data.count)).catch(() => {})
  }, [canRead])

  useEffect(() => {
    if (!open || !canRead) return
    void adminNotificationsApi.list({ limit: 15 }).then((res) => setItems(res.data)).catch(() => {})
  }, [open, canRead])

  useEffect(() => {
    if (!open) return
    const onDocClick = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [open])

  if (!canRead) return null

  return (
    <div className="relative" ref={panelRef}>
      <button type="button" aria-label="\u901a\u77e5" onClick={() => setOpen((v) => !v)} className="relative rounded-md p-2 text-gray-600 hover:bg-gray-100">
        <Bell className="h-5 w-5" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] rounded-full bg-red-500 px-1 text-[10px] font-bold text-white text-center">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-72 max-h-80 overflow-y-auto rounded-lg border bg-white shadow-lg">
          {items.length === 0 ? (
            <p className="px-4 py-6 text-sm text-gray-500">\u901a\u77e5\u306f\u3042\u308a\u307e\u305b\u3093</p>
          ) : (
            items.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`w-full text-left px-4 py-3 border-b text-sm hover:bg-gray-50 ${item.is_read ? '' : 'bg-amber-50'}`}
                onClick={() => {
                  if (!item.is_read) {
                    void adminNotificationsApi.markRead(item.id).then(() => {
                      setUnread((c) => Math.max(0, c - 1))
                      setItems((prev) => prev.map((n) => (n.id === item.id ? { ...n, is_read: true } : n)))
                    })
                  }
                  if (item.reference_type === 'order' && item.reference_id) {
                    window.location.href = `/admin/orders/${item.reference_id}`
                  }
                }}
              >
                <p className="font-medium">{item.title}</p>
                <p className="text-gray-600 mt-1 line-clamp-2">{item.body}</p>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
""",
    )

    w(
        "components/admin/AdminChrome.tsx",
        """'use client'

import Link from 'next/link'
import { LayoutDashboard } from 'lucide-react'
import { AdminNotificationBell } from '@/components/admin/AdminNotificationBell'

export function AdminChrome({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-white">
      <header className="sticky top-0 z-40 border-b border-gray-200 bg-white/95 backdrop-blur">
        <div className="container flex h-14 max-w-6xl items-center justify-between gap-4">
          <Link href="/admin" className="flex items-center gap-2 text-sm font-semibold text-gray-900 hover:text-yellow-600">
            <LayoutDashboard className="h-5 w-5 text-yellow-400" />
            \u7ba1\u7406\u753b\u9762
          </Link>
          <AdminNotificationBell />
        </div>
      </header>
      <main>{children}</main>
    </div>
  )
}
""",
    )

    fulfillment = f"""'use client'

import {{ useCallback, useEffect, useMemo, useState }} from 'react'
import Link from 'next/link'
import {{ ArrowLeft, Printer, RefreshCw, ScanLine, Truck }} from 'lucide-react'
import {{ useAdminGuard }} from '@/hooks/useAdminGuard'
import {{ adminApi }} from '@/lib/api'
import {{ Order }} from '@/lib/types'
import {{ Button }} from '@/components/ui/button'
import {{ shippingStatusLabel }} from '@/components/admin/AdminOrderShippingForm'

const PENDING_STATUSES = new Set(['unshipped', 'preparing', 'packing'])
const STATUS_LABELS: Record<string, string> = {{ packing: '{labels["packing"]}', in_transit: '{labels["in_transit"]}', received: '{labels["received"]}' }}

function labelForStatus(status: string | null | undefined): string {{
  if (!status) return '{dash}'
  return STATUS_LABELS[status] || shippingStatusLabel(status)
}}

function formatDateTime(iso: string | null | undefined): string {{
  if (!iso) return '{dash}'
  return new Date(iso).toLocaleString('ja-JP')
}}

export default function AdminFulfillmentPage() {{
  const {{ isReady }} = useAdminGuard()
  const [orders, setOrders] = useState<Order[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {{ setIsMounted(true) }}, [])

  const fetchOrders = useCallback(async () => {{
    setIsLoading(true)
    try {{
      const res = await adminApi.getAllOrders({{ payment_status: 'paid' }})
      setOrders((res.data || []).filter((o) => PENDING_STATUSES.has(o.shipping_status || 'unshipped')))
    }} finally {{
      setIsLoading(false)
    }}
  }}, [])

  useEffect(() => {{
    if (!isMounted || !isReady) return
    void fetchOrders()
  }}, [isMounted, isReady, fetchOrders])

  const counts = useMemo(() => {{
    const tally: Record<string, number> = {{}}
    for (const o of orders) {{
      const key = o.shipping_status || 'unshipped'
      tally[key] = (tally[key] || 0) + 1
    }}
    return tally
  }}, [orders])

  if (!isMounted || !isReady) return null

  return (
    <div className="container py-8 max-w-5xl">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div className="flex items-center gap-3">
          <Link href="/admin"><Button variant="ghost" size="icon" className="text-gray-400 hover:text-gray-900"><ArrowLeft className="h-4 w-4" /></Button></Link>
          <div className="flex items-center gap-2"><Truck className="h-6 w-6 text-orange-500" /><h1 className="text-2xl font-bold text-gray-900">\u767a\u9001\u7ba1\u7406</h1></div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/admin/orders/scan"><Button variant="outline" size="sm" className="gap-2"><ScanLine className="h-4 w-4" />\u6ce8\u6587\u30b9\u30ad\u30e3\u30f3</Button></Link>
          <Link href="/admin/click-post"><Button variant="outline" size="sm">\u30af\u30ea\u30c3\u30af\u30dd\u30b9\u30c8CSV</Button></Link>
          <Button variant="ghost" size="sm" className="gap-2" onClick={{() => void fetchOrders()}}><RefreshCw className="h-4 w-4" />\u66f4\u65b0</Button>
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        {{['unshipped', 'preparing', 'packing'].map((status) => (
          <div key={{status}} className="rounded-lg border bg-gray-50 px-4 py-3">
            <p className="text-xs text-gray-500">{{labelForStatus(status)}}</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{{counts[status] || 0}}</p>
          </div>
        ))}}
        <div className="rounded-lg border bg-orange-50 px-4 py-3">
          <p className="text-xs text-gray-500">\u5408\u8a08\uff08\u767a\u9001\u5f85\u3061\uff09</p>
          <p className="text-2xl font-bold text-orange-600 mt-1">{{orders.length}}</p>
        </div>
      </div>
      {{isLoading ? (
        <p className="text-gray-400 animate-pulse">\u8aad\u307f\u8fbc\u307f\u4e2d...</p>
      ) : orders.length === 0 ? (
        <p className="text-gray-500 rounded-lg border border-dashed p-8 text-center">\u767a\u9001\u5f85\u3061\u306e\u6ce8\u6587\u306f\u3042\u308a\u307e\u305b\u3093</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-gray-500">
              <tr>
                <th className="px-4 py-3 font-medium">\u6ce8\u6587</th>
                <th className="px-4 py-3 font-medium">\u30b9\u30c6\u30fc\u30bf\u30b9</th>
                <th className="px-4 py-3 font-medium">\u8cfc\u5165\u8005</th>
                <th className="px-4 py-3 font-medium">\u6ce8\u6587\u65e5\u6642</th>
                <th className="px-4 py-3 font-medium">\u64cd\u4f5c</th>
              </tr>
            </thead>
            <tbody>
              {{orders.map((order) => (
                <tr key={{order.id}} className="border-t hover:bg-gray-50/80">
                  <td className="px-4 py-3 font-mono">{{order.order_number || `#${{order.id}}`}}</td>
                  <td className="px-4 py-3">{{labelForStatus(order.shipping_status)}}</td>
                  <td className="px-4 py-3">{{order.buyer_name || order.buyer_email || '{dash}'}}</td>
                  <td className="px-4 py-3">{{formatDateTime(order.created_at)}}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2">
                      <Link href={{`/admin/orders/${{order.id}}`}}><Button variant="outline" size="sm">\u8a73\u7d30</Button></Link>
                      <Link href={{`/admin/orders/${{order.id}}/print/shipping-label`}}><Button variant="outline" size="sm" className="gap-1"><Printer className="h-3.5 w-3.5" />\u30e9\u30d9\u30eb</Button></Link>
                    </div>
                  </td>
                </tr>
              ))}}
            </tbody>
          </table>
        </div>
      )}}
    </div>
  )
}}
"""
    w("app/admin/fulfillment/page.tsx", fulfillment)

    scan = f"""'use client'

import {{ useCallback, useEffect, useState }} from 'react'
import Link from 'next/link'
import {{ ArrowLeft, ExternalLink }} from 'lucide-react'
import {{ useAdminGuard }} from '@/hooks/useAdminGuard'
import {{ adminOrderLogisticsApi }} from '@/lib/api'
import type {{ OrderScanResult }} from '@/lib/types'
import {{ BuybackBarcodeScanner }} from '@/components/admin/buyback/BuybackBarcodeScanner'
import {{ Button }} from '@/components/ui/button'
import {{ shippingStatusLabel }} from '@/components/admin/AdminOrderShippingForm'

const STATUS_LABELS: Record<string, string> = {{ packing: '{labels["packing"]}', in_transit: '{labels["in_transit"]}', received: '{labels["received"]}' }}

function labelForStatus(status: string | null | undefined): string {{
  if (!status) return '{dash}'
  return STATUS_LABELS[status] || shippingStatusLabel(status)
}}

function deviceInfo(): string {{
  return [navigator.userAgent || '', `viewport:${{window.innerWidth}}x${{window.innerHeight}}`].join(' | ').slice(0, 240)
}}

export default function AdminOrderScanPage() {{
  const {{ isReady }} = useAdminGuard()
  const [isMounted, setIsMounted] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<OrderScanResult | null>(null)

  useEffect(() => {{ setIsMounted(true) }}, [])

  const handleScan = useCallback(async (code: string) => {{
    setScanning(true)
    setError(null)
    try {{
      const res = await adminOrderLogisticsApi.scanOrder(code, deviceInfo())
      setResult(res.data)
    }} catch {{
      setError('\u6ce8\u6587\u304c\u898b\u3064\u304b\u308a\u307e\u305b\u3093\u3002\u30d0\u30fc\u30b3\u30fc\u30c9\u3092\u78ba\u8a8d\u3057\u3066\u304f\u3060\u3055\u3044\u3002')
      setResult(null)
    }} finally {{
      setScanning(false)
    }}
  }}, [])

  if (!isMounted || !isReady) return null

  return (
    <div className="container py-8 max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/admin/fulfillment"><Button variant="ghost" size="icon" className="text-gray-400 hover:text-gray-900"><ArrowLeft className="h-4 w-4" /></Button></Link>
        <h1 className="text-2xl font-bold text-gray-900">\u6ce8\u6587\u30b9\u30ad\u30e3\u30f3</h1>
      </div>
      <p className="text-sm text-gray-500 mb-4">\u6ce8\u6587\u30d0\u30fc\u30b3\u30fc\u30c9\u3092\u30b9\u30ad\u30e3\u30f3\u3059\u308b\u3068\u3001\u6ce8\u6587\u756a\u53f7\u30fb\u767a\u9001\u30b9\u30c6\u30fc\u30bf\u30b9\u3092\u8868\u793a\u3057\u307e\u3059\u3002</p>
      <BuybackBarcodeScanner onScan={{handleScan}} disabled={{scanning}} />
      {{error && <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{{error}}</p>}}
      {{result && (
        <div className="mt-6 rounded-xl border bg-gray-50 p-5 space-y-3">
          <h2 className="text-sm font-bold text-gray-700">\u30b9\u30ad\u30e3\u30f3\u7d50\u679c</h2>
          <dl className="grid grid-cols-[minmax(6rem,30%)_1fr] gap-2 text-sm">
            <dt className="text-gray-500">\u6ce8\u6587\u756a\u53f7</dt><dd className="font-mono">{{result.order_number || `#${{result.order_id}}`}}</dd>
            <dt className="text-gray-500">\u767a\u9001\u30b9\u30c6\u30fc\u30bf\u30b9</dt><dd>{{labelForStatus(result.shipping_status)}}</dd>
            <dt className="text-gray-500">\u8cfc\u5165\u8005</dt><dd>{{result.buyer_name || '{dash}'}}</dd>
            <dt className="text-gray-500">\u8ffd\u8de1\u756a\u53f7</dt><dd className="font-mono">{{result.tracking_number || '{dash}'}}</dd>
          </dl>
          <div className="flex flex-wrap gap-2 pt-2">
            <Link href={{`/admin/orders/${{result.order_id}}`}}><Button size="sm" className="gap-2"><ExternalLink className="h-4 w-4" />\u6ce8\u6587\u8a73\u7d30\u3092\u958b\u304f</Button></Link>
            <Link href={{`/admin/orders/${{result.order_id}}/print/shipping-label`}}><Button size="sm" variant="outline">\u767a\u9001\u30e9\u30d9\u30eb\u3092\u5370\u5237</Button></Link>
          </div>
        </div>
      )}}
    </div>
  )
}}
"""
    w("app/admin/orders/scan/page.tsx", scan)

    label = f"""'use client'

import {{ useCallback, useEffect, useState }} from 'react'
import Link from 'next/link'
import {{ useParams }} from 'next/navigation'
import {{ ArrowLeft, Loader2, Printer }} from 'lucide-react'
import {{ useAdminGuard }} from '@/hooks/useAdminGuard'
import {{ adminApi }} from '@/lib/api'
import {{ AdminOrderDetail }} from '@/lib/types'
import {{ Button }} from '@/components/ui/button'
import {{ shippingStatusLabel }} from '@/components/admin/AdminOrderShippingForm'

const STATUS_LABELS: Record<string, string> = {{ packing: '{labels["packing"]}', in_transit: '{labels["in_transit"]}', received: '{labels["received"]}' }}

function labelForStatus(status: string | null | undefined): string {{
  if (!status) return '{dash}'
  return STATUS_LABELS[status] || shippingStatusLabel(status)
}}

export default function AdminShippingLabelPrintPage() {{
  const params = useParams()
  const {{ isReady }} = useAdminGuard()
  const [order, setOrder] = useState<AdminOrderDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isMounted, setIsMounted] = useState(false)
  const orderId = Number(params.orderId)

  useEffect(() => {{ setIsMounted(true) }}, [])

  const fetchOrder = useCallback(async () => {{
    if (!Number.isFinite(orderId) || orderId <= 0) {{
      setError('\u7121\u52b9\u306a\u6ce8\u6587ID\u3067\u3059')
      setIsLoading(false)
      return
    }}
    setIsLoading(true)
    setError(null)
    try {{
      const res = await adminApi.getOrderById(orderId)
      setOrder(res.data)
    }} catch {{
      setError('\u6ce8\u6587\u306e\u53d6\u5f97\u306b\u5931\u6557\u3057\u307e\u3057\u305f')
      setOrder(null)
    }} finally {{
      setIsLoading(false)
    }}
  }}, [orderId])

  useEffect(() => {{
    if (!isMounted || !isReady) return
    void fetchOrder()
  }}, [isMounted, isReady, fetchOrder])

  if (!isMounted || !isReady) return null

  return (
    <div className="print-doc-wrapper min-h-screen bg-gray-100 py-6 px-4">
      <div className="no-print max-w-[100mm] mx-auto mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Link href={{`/admin/orders/${{orderId}}`}}><Button variant="ghost" size="sm" className="gap-1"><ArrowLeft className="h-4 w-4" />\u6ce8\u6587\u8a73\u7d30\u3078</Button></Link>
          <h1 className="text-sm font-medium text-gray-700">\u767a\u9001\u30e9\u30d9\u30eb\uff08\u5370\u5237\u30d7\u30ec\u30d3\u30e5\u30fc\uff09</h1>
        </div>
        <Button onClick={{() => window.print()}} disabled={{!order}} className="gap-2"><Printer className="h-4 w-4" />\u5370\u5237 / PDF\u4fdd\u5b58</Button>
      </div>
      {{isLoading && <div className="flex items-center justify-center gap-2 py-20 text-gray-400 no-print"><Loader2 className="h-5 w-5 animate-spin" />\u8aad\u307f\u8fbc\u307f\u4e2d...</div>}}
      {{!isLoading && error && <div className="no-print max-w-md mx-auto rounded-lg border border-red-200 bg-red-50 p-6 text-center text-red-700">{{error}}</div>}}
      {{!isLoading && order && (
        <div className="mx-auto w-[100mm] bg-white border shadow-sm p-4 print:shadow-none print:border-0">
          <p className="text-[10px] text-gray-500 uppercase tracking-wide">Shipping Label</p>
          <p className="text-lg font-bold font-mono mt-1">{{order.order_number || `#${{order.id}}`}}</p>
          <p className="text-xs text-gray-600 mt-2">{{labelForStatus(order.shipping_status)}}</p>
          <div className="mt-4 border-t pt-3 space-y-1 text-xs">
            <p className="font-medium">{{order.buyer_name || '{dash}'}}</p>
            <p>{{order.postal_code ? `\u3012${{order.postal_code}}` : ''}}</p>
            <p>{{order.region}}{{order.city}}{{order.address_line1}}</p>
            {{order.address_line2 && <p>{{order.address_line2}}</p>}}
            {{order.buyer_phone && <p>TEL: {{order.buyer_phone}}</p>}}
          </div>
          <div className="mt-4 flex justify-center">
            <img src={{`/api/admin/orders/${{order.id}}/barcode.svg`}} alt="Order barcode" className="max-w-full h-16 object-contain" />
          </div>
          {{order.tracking_number && <p className="text-center text-[10px] font-mono mt-2">\u8ffd\u8de1: {{order.tracking_number}}</p>}}
        </div>
      )}}
    </div>
  )
}}
"""
    w("app/admin/orders/[orderId]/print/shipping-label/page.tsx", label)


def write_playwright_e2e() -> None:
    """Write Playwright + Clerk testing files as UTF-8 (Windows-safe)."""
    root = ROOT / "frontend"

    def w(rel: str, content: str) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")

    w(
        "playwright.config.ts",
        """import { defineConfig, devices } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const envLocal = path.join(__dirname, '.env.local')
if (fs.existsSync(envLocal)) {
  for (const line of fs.readFileSync(envLocal, 'utf8').split(/\\r?\\n/)) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue
    const eq = trimmed.indexOf('=')
    const key = trimmed.slice(0, eq).trim()
    const value = trimmed.slice(eq + 1).trim().replace(/^['"]|['"]$/g, '')
    if (key && process.env[key] === undefined) process.env[key] = value
  }
}

const authFile = path.join(__dirname, 'playwright/.clerk/user.json')
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3000'

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [['list'], ['json', { outputFile: '../artifacts/phase2-manual-verify/playwright-report.json' }]],
  use: {
    baseURL,
    trace: 'on-first-retry',
    locale: 'ja-JP',
    timezoneId: 'Asia/Tokyo',
  },
  projects: [
    {
      name: 'global setup',
      testMatch: /global\\.setup\\.ts/,
    },
    {
      name: 'phase2-admin-ui',
      testMatch: /phase2-admin-ui\\.spec\\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        storageState: authFile,
      },
      dependencies: ['global setup'],
    },
  ],
})
""",
    )

    w(
        "e2e/global.setup.ts",
        """import { clerk, clerkSetup, setupClerkTestingToken } from '@clerk/testing/playwright'
import { test as setup, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'

setup.describe.configure({ mode: 'serial' })

const authFile = path.join(__dirname, '../playwright/.clerk/user.json')
const adminEmail =
  process.env.E2E_CLERK_USER_EMAIL ??
  process.env.PHASE1_ADMIN_EMAIL ??
  'rikukai0609@icloud.com'

setup('configure Clerk testing', async () => {
  await clerkSetup()
})

setup('authenticate admin and save storageState', async ({ page }) => {
  fs.mkdirSync(path.dirname(authFile), { recursive: true })
  if (fs.existsSync(authFile) && process.env.E2E_FORCE_REAUTH !== '1') {
    try {
      const state = JSON.parse(fs.readFileSync(authFile, 'utf8')) as { cookies?: unknown[] }
      if ((state.cookies?.length ?? 0) > 0) return
    } catch {
      // fall through to fresh sign-in
    }
  }

  await setupClerkTestingToken({ page })

  await page.goto('/sign-in', { waitUntil: 'domcontentloaded', timeout: 120_000 })
  await clerk.signIn({
    page,
    emailAddress: adminEmail,
  })

  await page.goto('/auth/after-sign-in', { waitUntil: 'domcontentloaded', timeout: 120_000 })
  await page.waitForURL(/\\/admin/, { timeout: 120_000 })

  await expect(page.getByText(/\\u7ba1\\u7406\\u30c0\\u30c3\\u30b7\\u30e5\\u30dc\\u30fc\\u30c9|\\u7ba1\\u7406\\u753b\\u9762|\\u767a\\u9001\\u7ba1\\u7406|\\u6ce8\\u6587\\u7ba1\\u7406/)).toBeVisible({
    timeout: 120_000,
  })

  await page.context().storageState({ path: authFile })
})
""",
    )

    w(
        "e2e/phase2-admin-ui.spec.ts",
        """import { test, expect } from '@playwright/test'
import fs from 'fs'
import path from 'path'

const outDir = path.join(__dirname, '../../artifacts/phase2-manual-verify')

test.describe.configure({ mode: 'serial' })

async function shot(page: import('@playwright/test').Page, name: string) {
  fs.mkdirSync(outDir, { recursive: true })
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: true })
}

async function waitAdminReady(page: import('@playwright/test').Page) {
  await expect(page).not.toHaveURL(/\\/sign-in/)
  await expect(
    page.getByText(/\\u7ba1\\u7406\\u30c0\\u30c3\\u30b7\\u30e5\\u30dc\\u30fc\\u30c9|\\u7ba1\\u7406\\u753b\\u9762|\\u767a\\u9001\\u7ba1\\u7406|\\u6ce8\\u6587\\u7ba1\\u7406|\\u8cb7\\u53d6\\u7533\\u8acb\\u7ba1\\u7406/).first(),
  ).toBeVisible({ timeout: 60_000 })
}

test('01 dashboard KPI (desktop)', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin')
  await waitAdminReady(page)
  await shot(page, '01-dashboard-kpi')
})

test('01 dashboard KPI (mobile)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/admin')
  await waitAdminReady(page)
  await shot(page, '01-dashboard-kpi-mobile')
})

test('02 notification bell open', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin')
  await waitAdminReady(page)
  const bell = page.getByRole('button', { name: '\\u901a\\u77e5' })
  await expect(bell).toBeVisible()
  await bell.click()
  await page.waitForTimeout(1000)
  await shot(page, '02-notification-bell-open')

  const unreadItem = page.locator('button.bg-amber-50').first()
  if ((await unreadItem.count()) > 0) {
    await unreadItem.click()
    await page.waitForTimeout(500)
    await shot(page, '02-notification-mark-read')
  }
})

test('03 fulfillment (desktop + mobile)', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin/fulfillment')
  await waitAdminReady(page)
  await expect(page.getByText('\\u767a\\u9001\\u7ba1\\u7406')).toBeVisible()
  await page.waitForSelector('table tbody tr, p:has-text("\\u767a\\u9001\\u5f85\\u3061\\u306e\\u6ce8\\u6587\\u306f\\u3042\\u308a\\u307e\\u305b\\u3093")', { timeout: 60_000 })
  await shot(page, '03-fulfillment')

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/admin/fulfillment')
  await waitAdminReady(page)
  await shot(page, '03-fulfillment-mobile')
})

test('04 order scan page', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin/orders/scan')
  await waitAdminReady(page)
  await expect(page.getByRole('heading', { name: '\\u6ce8\\u6587\\u30b9\\u30ad\\u30e3\\u30f3' })).toBeVisible()
  await shot(page, '04-order-scan')
})

test('08 buyback list CSV', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/admin/buyback/requests')
  await waitAdminReady(page)
  await shot(page, '08-buyback-list-csv')

  const csvBtn = page.getByRole('button', { name: /CSV/ })
  if ((await csvBtn.count()) > 0) {
    const downloadPromise = page.waitForEvent('download', { timeout: 60_000 })
    await csvBtn.first().click()
    const download = await downloadPromise
    const csvPath = path.join(outDir, 'buyback-export.csv')
    await download.saveAs(csvPath)
    const raw = fs.readFileSync(csvPath)
    expect(raw.slice(0, 3).equals(Buffer.from([0xef, 0xbb, 0xbf]))).toBeTruthy()
    await shot(page, '08-buyback-csv-clicked')
  }
})

test('05 order detail + shipment log, 06 label, 07 scan', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })

  let orderId: string | null = null
  await page.goto('/admin/fulfillment')
  await waitAdminReady(page)
  const orderLink = page.locator('a[href*="/admin/orders/"]').first()
  if ((await orderLink.count()) > 0) {
    const href = (await orderLink.getAttribute('href')) ?? ''
    const m = href.match(/\\/admin\\/orders\\/(\\d+)/)
    if (m) orderId = m[1]
  }

  if (!orderId) {
    await page.goto('/admin/orders')
    await waitAdminReady(page)
    const link = page.locator('a[href*="/admin/orders/"]').first()
    if ((await link.count()) > 0) {
      const href = (await link.getAttribute('href')) ?? ''
      const m = href.match(/\\/admin\\/orders\\/(\\d+)/)
      if (m) orderId = m[1]
    }
  }

  test.skip(!orderId, 'No order found for detail/label/scan checks')
  const oid = orderId!

  await page.goto(`/admin/orders/${oid}`)
  await waitAdminReady(page)
  await expect(page.getByText('\\u767a\\u9001\\u30ed\\u30b0')).toBeVisible({ timeout: 30_000 })
  await shot(page, '05-order-detail-shipment-log')

  await page.goto(`/admin/orders/${oid}/print/shipping-label`, { waitUntil: 'domcontentloaded', timeout: 120_000 })
  await waitAdminReady(page)
  const barcodeImg = page.locator('img[alt="Order barcode"]').first()
  await expect(barcodeImg).toBeVisible({ timeout: 90_000 })
  await expect
    .poll(async () => barcodeImg.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0))
    .toBeTruthy()
  await shot(page, '06-shipping-label-barcode')

  const barcodeEnsure = await page.request.get(`/api/admin/orders/${oid}/barcode`)
  expect(barcodeEnsure.ok()).toBeTruthy()
  const barcodeMeta = (await barcodeEnsure.json()) as {
    human_readable?: string | null
    order_id: number
  }
  const scanCode = barcodeMeta.human_readable?.trim() || `#${oid}`

  const scanApi = await page.request.post('/api/admin/orders/scan', {
    data: { code: scanCode },
  })
  expect(scanApi.ok()).toBeTruthy()
  const scanJson = (await scanApi.json()) as { order_id: number }
  expect(scanJson.order_id).toBe(Number(oid))
  expect(JSON.stringify(scanJson)).not.toContain('scan_token')

  await page.goto('/admin/orders/scan', { waitUntil: 'domcontentloaded', timeout: 120_000 })
  await waitAdminReady(page)
  const input = page.getByPlaceholder('\\u30d0\\u30fc\\u30b3\\u30fc\\u30c9\\u3092\\u30b9\\u30ad\\u30e3\\u30f3\\u307e\\u305f\\u306f\\u624b\\u5165\\u529b...')
  await input.fill(scanCode)
  await input.press('Enter')
  await expect(page.getByRole('heading', { name: '\\u30b9\\u30ad\\u30e3\\u30f3\\u7d50\\u679c' })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('\\u6ce8\\u6587\\u304c\\u898b\\u3064\\u304b\\u308a\\u307e\\u305b\\u3093')).toHaveCount(0)
  await shot(page, '07-barcode-scan-result')
})
""",
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--restore-phase2":
        restore_phase2_frontend()
        raise SystemExit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "--write-playwright-e2e":
        write_playwright_e2e()
        raise SystemExit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "--phase2-screenshots":
        print(
            "DEPRECATED: use TypeScript Playwright instead:\n"
            "  cd frontend && npm run test:e2e:setup && npm run test:e2e:phase2:full",
            file=sys.stderr,
        )
        raise SystemExit(2)
    raise SystemExit(main())