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

def clerk_sign_in(page, secret_key: str, report: dict) -> None:
    sign_in_url = get_sign_in_url(secret_key, ADMIN_EMAIL)
    if not sign_in_url:
        report["notes"].append("Clerk admin user not found")
        return
    page.goto(sign_in_url, wait_until="domcontentloaded", timeout=120000)
    for _ in range(30):
        if "/sign-in" not in page.url and "clerk" not in page.url.lower():
            break
        time.sleep(2)
    page.goto(f"{BASE_URL}/auth/after-sign-in", wait_until="domcontentloaded", timeout=120000)
    for _ in range(30):
        if page.url.rstrip("/").endswith("/admin") or "/admin/" in page.url:
            break
        time.sleep(2)
    report["after_sign_in_url"] = page.url

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

def phase2_main() -> int:
    load_dotenv(FRONTEND_ENV)
    secret_key = os.getenv("CLERK_SECRET_KEY", "").strip()
    from playwright.sync_api import sync_playwright

    out_dir = ROOT / "artifacts" / "phase2-screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "base_url": BASE_URL,
        "screenshots": [],
        "notes": [],
    }

    def shot2(page, name: str) -> None:
        out = out_dir / f"{name}.png"
        page.screenshot(path=str(out), full_page=True)
        body = page.inner_text("body")
        report["screenshots"].append(
            {
                "file": str(out.relative_to(ROOT)),
                "url": page.url,
                "title": page.title(),
                "is_sign_in": "/sign-in" in page.url,
                "has_admin_ui": any(t in body for t in ("管理ダッシュボード", "発送管理", "注文スキャン", "管理画面")),
            }
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, locale="ja-JP")
        if secret_key:
            clerk_sign_in(page, secret_key, report)
        else:
            report["notes"].append("CLERK_SECRET_KEY missing")
        for name, path in PHASE2_PAGES:
            try:
                page.goto(BASE_URL + path, wait_until="domcontentloaded", timeout=120000)
                time.sleep(2)
                shot2(page, name)
            except Exception as exc:
                report.setdefault("errors", {})[name] = str(exc)
        try:
            page.goto(BASE_URL + "/admin", wait_until="domcontentloaded", timeout=120000)
            time.sleep(2)
            bell = page.locator('button[aria-label="通知"]')
            if bell.count() > 0:
                bell.first.click()
                time.sleep(1)
                shot2(page, "04-notification-bell-open")
        except Exception as exc:
            report.setdefault("errors", {})["notification-bell-open"] = str(exc)
        try:
            page.goto(BASE_URL + "/admin/fulfillment", wait_until="domcontentloaded", timeout=120000)
            time.sleep(2)
            label_link = page.locator("a[href*='/print/shipping-label']").first
            if label_link.count() > 0:
                href = label_link.get_attribute("href")
                if href:
                    page.goto(BASE_URL + href, wait_until="domcontentloaded", timeout=120000)
                    time.sleep(2)
                    shot2(page, "05-shipping-label-barcode")
            else:
                report["notes"].append("No shipping-label link on fulfillment page")
        except Exception as exc:
            report.setdefault("errors", {})["shipping-label"] = str(exc)
        browser.close()
    (out_dir / "capture-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    safe = {k: v for k, v in report.items() if k != "screenshots"}
    safe["screenshot_count"] = len(report["screenshots"])
    safe["screenshot_files"] = [s["file"] for s in report["screenshots"]]
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0 if safe["screenshot_count"] > 0 else 1


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


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--restore-phase2":
        restore_phase2_frontend()
        raise SystemExit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "--phase2-screenshots":
        raise SystemExit(phase2_main())
    raise SystemExit(main())