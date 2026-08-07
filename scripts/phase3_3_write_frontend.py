"""Write Phase 3-3 live offers frontend (UTF-8 via path.write_text)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write(path: Path, content: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    size = path.stat().st_size
    print(f"wrote {path.relative_to(ROOT)} ({size} bytes)")
    return size

def patch_types() -> int:
    path = ROOT / "frontend/lib/types.ts"
    text = path.read_text(encoding="utf-8")
    if "export type LiveOfferStatus" in text:
        print("skip types.ts (already patched)")
        return path.stat().st_size
    marker = "export interface LiveBidPlaceResult {"
    idx = text.find(marker)
    if idx == -1:
        raise SystemExit("LiveBidPlaceResult marker not found")
    end = text.find("\n}\n", idx)
    if end == -1:
        raise SystemExit("LiveBidPlaceResult block end not found")
    insert_at = end + len("\n}\n")
    block = """

export type LiveOfferStatus = 'pending' | 'accepted' | 'rejected' | 'held' | 'expired' | 'cancelled'
export type LiveOfferPurchaseRightStatus = 'active' | 'used' | 'expired' | 'cancelled'

export interface LiveOfferProduct {
  id: number
  stream_id: number
  card_id: number
  display_price?: number | null
  card_name?: string | null
  card_image_url?: string | null
}

export interface LiveOfferPublic {
  id: number
  amount: number
  status: LiveOfferStatus
  sender_name?: string | null
  live_product_id: number
  product?: LiveOfferProduct | null
  created_at: string
}

export interface LiveOffer {
  id: number
  stream_id: number
  live_product_id: number
  user_id: number
  amount: number
  status: LiveOfferStatus
  review_note?: string | null
  reviewed_at?: string | null
  reviewed_by_admin_id?: number | null
  display_expires_at?: string | null
  purchase_expires_at?: string | null
  created_at: string
  updated_at?: string | null
  sender_name?: string | null
  product?: LiveOfferProduct | null
}

export interface LiveOfferList {
  items: LiveOffer[]
  total: number
}

export interface LiveOfferPublicList {
  items: LiveOfferPublic[]
  total: number
}

export interface LiveOfferSettings {
  shop_id: number
  purchase_window_seconds: number
  display_ttl_seconds: number
  max_amount: number
  rate_limit_count: number
  rate_limit_window_seconds: number
  offers_enabled: boolean
}

export interface LiveOfferPurchaseRight {
  id: number
  offer_id: number
  user_id: number
  live_product_id: number
  card_id: number
  accepted_price: number
  status: LiveOfferPurchaseRightStatus
  expires_at: string
  order_id?: number | null
  created_at: string
}

export interface LiveOfferPurchaseResult {
  order_id: number
  purchase_right: LiveOfferPurchaseRight
}
"""
    text = text[:insert_at] + block + text[insert_at:]
    if "offers_enabled?: boolean" not in text:
        text = text.replace(
            "  is_pinned: boolean\n  card_name?: string | null",
            "  is_pinned: boolean\n  offers_enabled?: boolean\n  card_name?: string | null",
            1,
        )
        text = text.replace(
            "  comment_count: number\n}",
            "  comment_count: number\n  offers_enabled?: boolean\n}",
            1,
        )
    return write(path, text)
def patch_api() -> int:
    path = ROOT / "frontend/lib/api.ts"
    text = path.read_text(encoding="utf-8")
    if "adminLiveOfferApi" in text:
        print("skip api.ts (already patched)")
        return path.stat().st_size
    old = """  if (url.includes('/auctions/') && url.includes('/bids')) return true
  return false"""
    new = """  if (url.includes('/auctions/') && url.includes('/bids')) return true
  if (url.includes('/offers')) return true
  return false"""
    if old not in text:
        raise SystemExit("needsLiveUserAuth block not found")
    text = text.replace(old, new, 1)
    offer_api = """

export const adminLiveOfferApi = {
  getSettings: (streamId: number) =>
    apiClient.get<import('./types').LiveOfferSettings>(`/admin/live/streams/${streamId}/offers/settings`),
  patchSettings: (streamId: number, data: Partial<import('./types').LiveOfferSettings>) =>
    apiClient.patch<import('./types').LiveOfferSettings>(`/admin/live/streams/${streamId}/offers/settings`, data),
  patchProductOffersEnabled: (streamId: number, productId: number, offers_enabled: boolean) =>
    apiClient.patch<{ id: number; offers_enabled: boolean }>(
      `/admin/live/streams/${streamId}/products/${productId}/offers`,
      { offers_enabled },
    ),
  listOffers: (
    streamId: number,
    params?: { status?: string; sort?: string; order?: string; limit?: number; offset?: number },
  ) => apiClient.get<import('./types').LiveOfferList>(`/admin/live/streams/${streamId}/offers`, { params }),
  getOffer: (streamId: number, offerId: number) =>
    apiClient.get<import('./types').LiveOffer>(`/admin/live/streams/${streamId}/offers/${offerId}`),
  accept: (streamId: number, offerId: number, review_note?: string) =>
    apiClient.post<import('./types').LiveOffer>(
      `/admin/live/streams/${streamId}/offers/${offerId}/accept`,
      review_note ? { review_note } : {},
    ),
  reject: (streamId: number, offerId: number, review_note?: string) =>
    apiClient.post<import('./types').LiveOffer>(
      `/admin/live/streams/${streamId}/offers/${offerId}/reject`,
      review_note ? { review_note } : {},
    ),
  hold: (streamId: number, offerId: number, review_note?: string) =>
    apiClient.post<import('./types').LiveOffer>(
      `/admin/live/streams/${streamId}/offers/${offerId}/hold`,
      review_note ? { review_note } : {},
    ),
}

export const liveOfferApi = {
  listPublic: (streamId: number, params?: { limit?: number; offset?: number }) =>
    apiClient.get<import('./types').LiveOfferPublicList>(`/live/streams/${streamId}/offers`, { params }),
  listMine: (streamId: number, params?: { status?: string; limit?: number; offset?: number }) =>
    apiClient.get<import('./types').LiveOfferList>(`/live/streams/${streamId}/offers/mine`, { params }),
  create: (
    streamId: number,
    data: { live_product_id: number; amount: number; idempotency_key?: string },
  ) => apiClient.post<import('./types').LiveOffer>(`/live/streams/${streamId}/offers`, data),
  getPurchaseRight: (offerId: number) =>
    apiClient.get<import('./types').LiveOfferPurchaseRight>(`/live/offers/${offerId}/purchase-right`),
  purchase: (offerId: number, data?: Record<string, unknown>) =>
    apiClient.post<import('./types').LiveOfferPurchaseResult>(`/live/offers/${offerId}/purchase`, data ?? {}),
}
"""
    text = text.rstrip() + offer_api + "\n"
    return write(path, text)
def patch_playwright() -> int:
    path = ROOT / "frontend/playwright.config.ts"
    text = path.read_text(encoding="utf-8")
    if "phase3-3-offers" in text:
        print("skip playwright.config.ts (already patched)")
        return path.stat().st_size
    if "phase3-3-offers/playwright-report.json" not in text:
        text = text.replace(
            "  reporter: [['list'], ['json', { outputFile: '../artifacts/phase3-2-milestone1/playwright-report.json' }]],",
            "  reporter: [\n    ['list'],\n    ['json', { outputFile: '../artifacts/phase3-2-milestone1/playwright-report.json' }],\n    ['json', { outputFile: '../artifacts/phase3-3-offers/playwright-report.json' }],\n  ],",
            1,
        )
    project = """
    {
      name: 'phase3-3-offers',
      testMatch: /phase3-3-offers\\.spec\\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        storageState: authFile,
      },
      dependencies: ['global setup'],
    },
"""
    text = text.replace("  ],\n})\n", project + "  ],\n})\n", 1)
    return write(path, text)


def patch_admin_detail() -> int:
    path = ROOT / "frontend/app/admin/live/[id]/page.tsx"
    text = path.read_text(encoding="utf-8")
    if "\u5e0c\u671b\u984d\u7ba1\u7406" in text and "offersSettings" in text:
        print("skip admin live detail (already patched)")
        return path.stat().st_size
    text = text.replace(
        "import { adminLiveApi } from '@/lib/api'",
        "import { adminLiveApi, adminLiveOfferApi } from '@/lib/api'",
        1,
    )
    text = text.replace(
        "import type { LiveComment, LiveProduct, LiveStream } from '@/lib/types'",
        "import type { LiveComment, LiveOfferSettings, LiveProduct, LiveStream } from '@/lib/types'",
        1,
    )
    if "offersSettings" not in text:
        text = text.replace(
            "  const [ngWords, setNgWords] = useState<{ id: number; word: string; is_active: boolean }[]>([])\n",
            "  const [ngWords, setNgWords] = useState<{ id: number; word: string; is_active: boolean }[]>([])\n  const [offersSettings, setOffersSettings] = useState<LiveOfferSettings | null>(null)\n",
            1,
        )
    if "adminLiveOfferApi.getSettings" not in text:
        text = text.replace(
            "    setComments(c.data.items)\n    if (hasPermission('live.moderate')) {",
            "    setComments(c.data.items)\n    if (hasPermission('offer.read') || hasPermission('offer.manage')) {\n      adminLiveOfferApi.getSettings(streamId).then((res) => setOffersSettings(res.data)).catch(() => undefined)\n    }\n    if (hasPermission('live.moderate')) {",
            1,
        )
    auction_link = "          <Link href={`/admin/live/${stream.id}/auctions`} className=\"inline-flex items-center gap-1 text-sm text-amber-700 hover:underline\">\n            \u30aa\u30fc\u30af\u30b7\u30e7\u30f3\u7ba1\u7406\n          </Link>"
    if "/offers`" not in text and auction_link in text:
        text = text.replace(
            auction_link,
            auction_link
            + "\n          <Link href={`/admin/live/${stream.id}/offers`} className=\"inline-flex items-center gap-1 text-sm text-emerald-700 hover:underline\">\n            \u5e0c\u671b\u984d\u7ba1\u7406\n          </Link>",
            1,
        )
    if "offersSettings != null" not in text:
        text = text.replace(
            "          <span className=\"rounded-full bg-gray-100 dark:bg-gray-800 px-3 py-1 text-sm\">{stream.status}</span>\n",
            "          <span className=\"rounded-full bg-gray-100 dark:bg-gray-800 px-3 py-1 text-sm\">{stream.status}</span>\n          {offersSettings != null && (\n            <span className=\"rounded-full bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-200 px-3 py-1 text-sm\">\n              \u5e0c\u671b\u984d {offersSettings.offers_enabled ? 'ON' : 'OFF'}\n            </span>\n          )}\n",
            1,
        )
    return write(path, text)
def write_admin_offers_page() -> int:
    src = ROOT / "scripts/_p33_admin_offers_page.tsx"
    dest = ROOT / "frontend/app/admin/live/[id]/offers/page.tsx"
    return write(dest, src.read_text(encoding="utf-8"))


def patch_live_page() -> int:
    path = ROOT / "frontend/app/live/[id]/page.tsx"
    text = path.read_text(encoding="utf-8")
    if "liveOfferApi" in text and "live-offers-panel" in text:
        print("skip live page (already patched)")
        return path.stat().st_size

    text = text.replace(
        "import { liveApi, liveAuctionApi } from '@/lib/api'",
        "import { liveApi, liveAuctionApi, liveOfferApi } from '@/lib/api'",
        1,
    )
    text = text.replace(
        "import type { LiveAuction, LiveBid, LiveComment, LiveStream } from '@/lib/types'",
        "import type { LiveAuction, LiveBid, LiveComment, LiveOffer, LiveOfferPublic, LiveStream } from '@/lib/types'",
        1,
    )

    helper = """

function formatDisplayExpiry(expiresAt?: string | null, nowMs = Date.now()): string {
  if (!expiresAt) return ''
  const ms = new Date(expiresAt).getTime() - nowMs
  if (ms <= 0) return '\u8868\u793a\u7d42\u4e86'
  const total = Math.floor(ms / 1000)
  const m = Math.floor(total / 60)
  const s = total % 60
  return `\u6b8b\u308a ${m}:${s.toString().padStart(2, '0')}`
}

function offerStatusMessage(status: LiveOffer['status']): string {
  if (status === 'accepted') return '\u627f\u8a8d\u3055\u308c\u307e\u3057\u305f\u3002\u3054\u8cfc\u5165\u3044\u305f\u3060\u3051\u307e\u3059\u3002'
  if (status === 'rejected') return '\u5374\u4e0b\u3055\u308c\u307e\u3057\u305f\u3002'
  if (status === 'held') return '\u4fdd\u7559\u4e2d\u3067\u3059\u3002\u3057\u3070\u3089\u304f\u304a\u5f85\u3061\u304f\u3060\u3055\u3044\u3002'
  if (status === 'pending') return '\u5be9\u67fb\u4e2d\u3067\u3059\u3002'
  return status
}
"""
    if "formatDisplayExpiry" not in text:
        text = text.replace("function minNextBid(auction: LiveAuction): number {", helper + "\nfunction minNextBid(auction: LiveAuction): number {", 1)

    state_block = """
  const [publicOffers, setPublicOffers] = useState<LiveOfferPublic[]>([])
  const [myOffers, setMyOffers] = useState<LiveOffer[]>([])
  const [offerAmount, setOfferAmount] = useState('1500')
  const [offerError, setOfferError] = useState('')
  const [offerPurchaseMessage, setOfferPurchaseMessage] = useState('')
  const [offersEnabled, setOffersEnabled] = useState(true)
"""
    if "publicOffers" not in text:
        text = text.replace("  const [nowMs, setNowMs] = useState(() => Date.now())\n", "  const [nowMs, setNowMs] = useState(() => Date.now())\n" + state_block, 1)

    reload_block = """
  const reloadPublicOffers = useCallback(() => {
    return liveOfferApi.listPublic(streamId, { limit: 30 }).then((res) => setPublicOffers(res.data.items))
  }, [streamId])

  const reloadMyOffers = useCallback(() => {
    return liveOfferApi.listMine(streamId, { limit: 20 }).then((res) => setMyOffers(res.data.items))
  }, [streamId])

  const latestMyOffer = useMemo(() => myOffers[0] ?? null, [myOffers])

  const offersFormVisible = useMemo(() => {
    const product = stream?.active_product || stream?.pinned_product
    if (!product || !offersEnabled) return false
    if (stream?.status !== 'live' && stream?.status !== 'paused') return false
    if (product.offers_enabled === false) return false
    if (stream?.offers_enabled === false) return false
    return true
  }, [stream, offersEnabled])
"""
    if "reloadPublicOffers" not in text:
        text = text.replace("  const reloadBids = useCallback(", reload_block + "\n  const reloadBids = useCallback(", 1)

    init_effect = """
    reloadPublicOffers().catch(() => undefined)
    reloadMyOffers().catch(() => undefined)
"""
    if "reloadPublicOffers()" not in text.split("reloadAuctions().catch")[0]:
        text = text.replace("    reloadAuctions().catch(() => undefined)\n", "    reloadAuctions().catch(() => undefined)\n" + init_effect, 1)

    stream_effect = """
  useEffect(() => {
    if (stream?.offers_enabled === false) setOffersEnabled(false)
    else if (stream?.offers_enabled === true) setOffersEnabled(true)
  }, [stream?.offers_enabled])
"""
    if "stream?.offers_enabled" not in text:
        text = text.replace("  useEffect(() => {\n    const timer = window.setInterval(() => setNowMs(Date.now()), 1000)", stream_effect + "\n  useEffect(() => {\n    const timer = window.setInterval(() => setNowMs(Date.now()), 1000)", 1)

    upsert_offer = """
  const upsertPublicOffer = useCallback((offer: LiveOfferPublic) => {
    setPublicOffers((prev) => {
      const idx = prev.findIndex((o) => o.id === offer.id)
      if (idx === -1) return [offer, ...prev]
      return prev.map((o) => (o.id === offer.id ? offer : o))
    })
  }, [])

  const upsertMyOffer = useCallback((offer: LiveOffer) => {
    setMyOffers((prev) => {
      const idx = prev.findIndex((o) => o.id === offer.id)
      if (idx === -1) return [offer, ...prev]
      return prev.map((o) => (o.id === offer.id ? offer : o))
    })
  }, [])
"""
    if "upsertPublicOffer" not in text:
        text = text.replace("  const upsertAuction = useCallback((auction: LiveAuction) => {", upsert_offer + "\n  const upsertAuction = useCallback((auction: LiveAuction) => {", 1)

    offer_events = """
      if (evt.type.startsWith('offer.')) {
        const payload = evt.payload as unknown as LiveOffer
        const pub: LiveOfferPublic = {
          id: payload.id,
          amount: payload.amount,
          status: payload.status,
          sender_name: payload.sender_name,
          live_product_id: payload.live_product_id,
          product: payload.product,
          created_at: payload.created_at,
        }
        upsertPublicOffer(pub)
        upsertMyOffer(payload)
        reloadMyOffers().catch(() => undefined)
        return
      }
"""
    if "evt.type.startsWith('offer.')" not in text:
        text = text.replace("      if (evt.type.startsWith('bid.')) {", offer_events + "\n      if (evt.type.startsWith('bid.')) {", 1)

    deps_old = "    [streamId, activeAuction?.id, upsertAuction, reloadBids],"
    deps_new = "    [streamId, activeAuction?.id, upsertAuction, reloadBids, upsertPublicOffer, upsertMyOffer, reloadMyOffers],"
    text = text.replace(deps_old, deps_new, 1)

    submit_offer = """
  const submitOffer = async () => {
    const product = stream?.active_product || stream?.pinned_product
    if (!product) return
    setOfferError('')
    const amount = Number(offerAmount)
    if (!Number.isFinite(amount) || amount <= 0) {
      setOfferError('\u91d1\u984d\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044')
      return
    }
    try {
      const res = await liveOfferApi.create(streamId, {
        live_product_id: product.id,
        amount,
      })
      upsertMyOffer(res.data)
      await reloadPublicOffers()
      setOfferAmount(String(amount))
    } catch {
      setOfferError('\u5e0c\u671b\u984d\u306e\u9001\u4fe1\u306b\u5931\u6557\u3057\u307e\u3057\u305f')
    }
  }

  const purchaseAcceptedOffer = async () => {
    if (!latestMyOffer || latestMyOffer.status !== 'accepted') return
    setOfferPurchaseMessage('')
    try {
      const res = await liveOfferApi.purchase(latestMyOffer.id, { shipping_address: 'E2E Offer Purchase' })
      setOfferPurchaseMessage(`\u6ce8\u6587 #${res.data.order_id} \u3092\u4f5c\u6210\u3057\u307e\u3057\u305f`)
    } catch {
      setOfferPurchaseMessage('\u8cfc\u5165\u306b\u5931\u6557\u3057\u307e\u3057\u305f')
    }
  }
"""
    if "submitOffer" not in text:
        text = text.replace("  const submitBid = async () => {", submit_offer + "\n  const submitBid = async () => {", 1)

    offers_jsx = """
          <div data-testid="live-offers-panel" className="rounded-xl border border-emerald-700/40 bg-emerald-950/20 p-4 mb-4 min-h-[280px] flex flex-col">
            <h2 className="font-semibold mb-3 text-emerald-200 text-lg">\u5e0c\u671b\u984d</h2>
            <ul className="space-y-2 flex-1 overflow-y-auto max-h-52 mb-4 text-sm">
              {publicOffers.map((o) => (
                <li key={o.id} className="flex justify-between gap-2 border-b border-gray-800/60 py-1">
                  <span className="text-gray-300 truncate">{o.sender_name || '\u30e6\u30fc\u30b6\u30fc'} \u00b7 {o.status}</span>
                  <span className="font-medium">\u00a5{o.amount.toLocaleString('ja-JP')}</span>
                </li>
              ))}
              {publicOffers.length === 0 && <li className="text-gray-500">\u5e0c\u671b\u984d\u306f\u3042\u308a\u307e\u305b\u3093</li>}
            </ul>
            <p className="text-xs text-gray-500 mb-3">\u8868\u793a\u671f\u9650\u306f\u30ab\u30fc\u30c9\u306b\u8868\u793a\u3055\u308c\u307f\u3059</p>

            {offersFormVisible && (
              <div className="flex gap-2 mb-4">
                <input
                  data-testid="offer-amount-input"
                  value={offerAmount}
                  onChange={(e) => setOfferAmount(e.target.value)}
                  className="flex-1 rounded-lg bg-gray-900 border border-gray-700 px-3 py-2"
                />
                <button data-testid="offer-submit" type="button" onClick={submitOffer} className="rounded-lg bg-emerald-600 px-4 py-2 font-medium">
                  \u63d0\u51fa
                </button>
              </div>
            )}
            {offerError && <p className="text-red-400 text-sm mb-2">{offerError}</p>}

            {latestMyOffer && (
              <div data-testid="offer-my-status" className="rounded-lg border border-gray-700 bg-black/30 p-3 text-sm">
                <p className="font-medium text-emerald-200">\u3042\u306a\u305f\u306e\u5e0c\u671b\u984d: \u00a5{latestMyOffer.amount.toLocaleString('ja-JP')}</p>
                <p className="text-gray-300 mt-1">{offerStatusMessage(latestMyOffer.status)}</p>
                {latestMyOffer.display_expires_at && latestMyOffer.status === 'pending' && (
                  <p className="text-xs text-gray-500 mt-1">{formatDisplayExpiry(latestMyOffer.display_expires_at, nowMs)}</p>
                )}
                {latestMyOffer.status === 'accepted' && (
                  <button
                    data-testid="offer-purchase"
                    type="button"
                    onClick={purchaseAcceptedOffer}
                    className="mt-3 rounded-lg bg-yellow-500 text-gray-900 px-4 py-2 font-medium"
                  >
                    \u627f\u8a8d\u984d\u3067\u8cfc\u5165
                  </button>
                )}
                {offerPurchaseMessage && <p className="text-emerald-300 mt-2">{offerPurchaseMessage}</p>}
              </div>
            )}
          </div>
"""
    anchor = "          {activeAuction && ("
    if "live-offers-panel" not in text:
        text = text.replace(anchor, offers_jsx + "\n" + anchor, 1)

    comment_section = "        <section className=\"flex flex-col min-h-[420px]\">"
    if comment_section in text:
        text = text.replace(comment_section, "        <section className=\"flex flex-col min-h-[320px] lg:min-h-[420px]\">", 1)

    # decode unicode escapes inserted above for TS/JS string literals - keep as \u in python source is fine for write
    import re
    text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)

    return write(path, text)
def write_e2e_spec() -> int:
    src = ROOT / "scripts/_p33_e2e.spec.ts"
    dest = ROOT / "frontend/e2e/phase3-3-offers.spec.ts"
    return write(dest, src.read_text(encoding="utf-8"))


def main() -> None:
    sizes: dict[str, int] = {}
    sizes["frontend/lib/types.ts"] = patch_types()
    sizes["frontend/lib/api.ts"] = patch_api()
    sizes["frontend/playwright.config.ts"] = patch_playwright()
    sizes["frontend/app/admin/live/[id]/page.tsx"] = patch_admin_detail()
    sizes["frontend/app/admin/live/[id]/offers/page.tsx"] = write_admin_offers_page()
    sizes["frontend/app/live/[id]/page.tsx"] = patch_live_page()
    sizes["frontend/e2e/phase3-3-offers.spec.ts"] = write_e2e_spec()
    print("--- summary ---")
    for k, v in sizes.items():
        print(f"{k}: {v} bytes")


if __name__ == "__main__":
    main()
