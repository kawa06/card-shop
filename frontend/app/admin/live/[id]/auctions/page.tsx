'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Gavel, Pause, Play, Square, XCircle } from 'lucide-react'
import { useParams } from 'next/navigation'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminLiveApi, adminLiveAuctionApi } from '@/lib/api'
import { getClerkSessionToken } from '@/lib/clerk-token'
import { useLiveEventSource } from '@/hooks/useLiveEventSource'
import type { LiveAuction, LiveProduct, LiveStream } from '@/lib/types'

function formatRemaining(endsAt?: string | null, nowMs = Date.now()): string {
  if (!endsAt) return '—'
  const ms = new Date(endsAt).getTime() - nowMs
  if (ms <= 0) return '0:00'
  const total = Math.floor(ms / 1000)
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

function formatYen(value: number): string {
  return `¥${value.toLocaleString('ja-JP')}`
}

export default function AdminLiveAuctionsPage() {
  const params = useParams<{ id: string }>()
  const streamId = Number(params.id)
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const canRead = hasPermission('auction.read')
  const canWrite = hasPermission('auction.write')
  const canManage = hasPermission('auction.manage')

  const [stream, setStream] = useState<LiveStream | null>(null)
  const [products, setProducts] = useState<LiveProduct[]>([])
  const [auctions, setAuctions] = useState<LiveAuction[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [bids, setBids] = useState<{ id: number; amount: number; user_id: number; created_at: string }[]>([])
  const [nowMs, setNowMs] = useState(() => Date.now())

  const [liveProductId, setLiveProductId] = useState('')
  const [startPrice, setStartPrice] = useState('1000')
  const [increment, setIncrement] = useState('100')
  const [buyNow, setBuyNow] = useState('5000')
  const [durationSeconds, setDurationSeconds] = useState('120')

  const selected = useMemo(
    () => auctions.find((a) => a.id === selectedId) ?? null,
    [auctions, selectedId],
  )

  const reloadAuctions = useCallback(async () => {
    const res = await adminLiveAuctionApi.list(streamId, { limit: 50 })
    setAuctions(res.data.items)
    if (selectedId != null && !res.data.items.some((a) => a.id === selectedId)) {
      setSelectedId(res.data.items[0]?.id ?? null)
    }
  }, [streamId, selectedId])

  const reload = useCallback(async () => {
    const [s, p, a] = await Promise.all([
      adminLiveApi.getStream(streamId),
      adminLiveApi.listProducts(streamId),
      adminLiveAuctionApi.list(streamId, { limit: 50 }),
    ])
    setStream(s.data)
    setProducts(p.data)
    setAuctions(a.data.items)
    if (liveProductId === '' && p.data[0]) setLiveProductId(String(p.data[0].id))
  }, [streamId, liveProductId])

  useEffect(() => {
    if (!isReady || !canRead || !streamId) return
    reload().catch(() => undefined)
  }, [isReady, canRead, streamId, reload])

  useEffect(() => {
    if (!selectedId || !canRead) {
      setBids([])
      return
    }
    adminLiveAuctionApi
      .listBids(streamId, selectedId, { limit: 20 })
      .then((res) => setBids(res.data.items))
      .catch(() => setBids([]))
  }, [streamId, selectedId, canRead])

  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  const upsertAuction = useCallback((auction: LiveAuction) => {
    setAuctions((prev) => {
      const idx = prev.findIndex((a) => a.id === auction.id)
      if (idx === -1) return [auction, ...prev]
      return prev.map((a) => (a.id === auction.id ? auction : a))
    })
  }, [])

  const getAuthHeaders = useCallback(async (): Promise<Record<string, string>> => {
    const token = await getClerkSessionToken()
    return token ? { Authorization: `Bearer ${token}` } : {}
  }, [])

  const onLiveEvent = useCallback(
    (evt: { type: string; payload: Record<string, unknown> }) => {
      if (evt.type.startsWith('auction.')) {
        upsertAuction(evt.payload as unknown as LiveAuction)
        return
      }
      if (evt.type.startsWith('bid.')) {
        const auctionId = Number(evt.payload.auction_id)
        if (selectedId === auctionId) {
          adminLiveAuctionApi
            .listBids(streamId, auctionId, { limit: 20 })
            .then((res) => setBids(res.data.items))
            .catch(() => undefined)
        }
        adminLiveAuctionApi
          .get(streamId, auctionId)
          .then((res) => upsertAuction(res.data))
          .catch(() => undefined)
      }
    },
    [streamId, selectedId, upsertAuction],
  )

  useLiveEventSource(
    isReady && canRead ? `/api/admin/live/streams/${streamId}/events` : null,
    onLiveEvent,
    { getAuthHeaders },
  )

  const createAuction = async () => {
    if (!canWrite || !liveProductId) return
    const created = await adminLiveAuctionApi.create(streamId, {
      live_product_id: Number(liveProductId),
      start_price: Number(startPrice),
      min_bid_increment: Number(increment),
      buy_now_price: buyNow ? Number(buyNow) : undefined,
      duration_seconds: durationSeconds ? Number(durationSeconds) : undefined,
    })
    upsertAuction(created.data)
    setSelectedId(created.data.id)
  }

  const runAction = async (action: 'start' | 'pause' | 'resume' | 'finish' | 'cancel') => {
    if (!selected || !canManage) return
    let res
    if (action === 'start') res = await adminLiveAuctionApi.start(streamId, selected.id)
    else if (action === 'pause') res = await adminLiveAuctionApi.pause(streamId, selected.id)
    else if (action === 'resume') res = await adminLiveAuctionApi.resume(streamId, selected.id)
    else if (action === 'finish') res = await adminLiveAuctionApi.finish(streamId, selected.id)
    else res = await adminLiveAuctionApi.cancel(streamId, selected.id)
    upsertAuction(res.data)
  }

  if (!isReady || !canRead) return null
  if (!stream) return <div className="min-h-screen bg-white p-8">読み込み中...</div>

  const currentPrice = selected?.current_price ?? selected?.start_price ?? 0

  return (
    <div className="min-h-screen bg-white dark:bg-gray-950">
      <div className="container py-8 max-w-6xl">
        <div className="flex flex-wrap items-center gap-3 mb-6">
          <Link href={`/admin/live/${streamId}`} className="text-gray-500 hover:text-gray-900 dark:hover:text-gray-100">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <Gavel className="h-6 w-6 text-amber-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">オークション管理</h1>
          <span className="text-sm text-gray-500">{stream.title}</span>
          <Link href={`/admin/live/${streamId}`} className="ml-auto text-sm text-amber-700 hover:underline">
            配信に戻る
          </Link>
        </div>

        <div className="grid gap-8 lg:grid-cols-[1fr_1.2fr]">
          <section>
            <h2 className="font-semibold mb-3 text-gray-900 dark:text-gray-100">オークション一覧</h2>
            <ul className="space-y-2 mb-8">
              {auctions.map((a) => (
                <li key={a.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(a.id)}
                    className={`w-full rounded-lg border p-3 text-left text-sm dark:border-gray-800 ${selectedId === a.id ? 'border-amber-500 bg-amber-50 dark:bg-amber-950/20' : ''}`}
                  >
                    <div className="flex justify-between gap-2">
                      <span className="font-medium">#{a.id} {a.product?.card_name || `Product ${a.live_product_id}`}</span>
                      <span className="text-gray-500">{a.status}</span>
                    </div>
                    <p className="mt-1 text-gray-600 dark:text-gray-300">
                      {formatYen(a.current_price ?? a.start_price)} · 入札 {a.bid_count}件
                    </p>
                  </button>
                </li>
              ))}
              {auctions.length === 0 && <p className="text-sm text-gray-500">まだオークションがありません</p>}
            </ul>

            {canWrite && (
              <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-4">
                <h3 className="font-semibold mb-3 text-gray-900 dark:text-gray-100">新規オークション</h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="text-sm sm:col-span-2">
                    <span className="block mb-1 text-gray-600 dark:text-gray-300">商品</span>
                    <select
                      value={liveProductId}
                      onChange={(e) => setLiveProductId(e.target.value)}
                      className="w-full rounded-lg border px-3 py-2 dark:bg-gray-900 dark:border-gray-700"
                    >
                      {products.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.card_name || `Card #${p.card_id}`}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-sm">
                    <span className="block mb-1 text-gray-600 dark:text-gray-300">開始価格</span>
                    <input value={startPrice} onChange={(e) => setStartPrice(e.target.value)} className="w-full rounded-lg border px-3 py-2 dark:bg-gray-900 dark:border-gray-700" />
                  </label>
                  <label className="text-sm">
                    <span className="block mb-1 text-gray-600 dark:text-gray-300">最小入札単位</span>
                    <input value={increment} onChange={(e) => setIncrement(e.target.value)} className="w-full rounded-lg border px-3 py-2 dark:bg-gray-900 dark:border-gray-700" />
                  </label>
                  <label className="text-sm">
                    <span className="block mb-1 text-gray-600 dark:text-gray-300">即決価格</span>
                    <input value={buyNow} onChange={(e) => setBuyNow(e.target.value)} className="w-full rounded-lg border px-3 py-2 dark:bg-gray-900 dark:border-gray-700" />
                  </label>
                  <label className="text-sm">
                    <span className="block mb-1 text-gray-600 dark:text-gray-300">時間（秒）</span>
                    <input value={durationSeconds} onChange={(e) => setDurationSeconds(e.target.value)} className="w-full rounded-lg border px-3 py-2 dark:bg-gray-900 dark:border-gray-700" />
                  </label>
                </div>
                <button type="button" onClick={() => createAuction().catch(() => undefined)} className="mt-4 rounded-lg bg-gray-900 text-white px-4 py-2 text-sm dark:bg-gray-100 dark:text-gray-900">
                  作成
                </button>
              </div>
            )}
          </section>

          <section className="rounded-xl border border-gray-200 dark:border-gray-800 p-4">
            {!selected ? (
              <p className="text-sm text-gray-500">オークションを選択してください</p>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-2 mb-4">
                  <h2 className="font-semibold text-gray-900 dark:text-gray-100">#{selected.id}</h2>
                  <span className="rounded-full bg-gray-100 dark:bg-gray-800 px-3 py-1 text-sm">{selected.status}</span>
                </div>
                <dl className="grid grid-cols-2 gap-3 text-sm mb-6">
                  <div>
                    <dt className="text-gray-500">現在価格</dt>
                    <dd className="text-xl font-bold text-amber-700 dark:text-amber-400">{formatYen(currentPrice)}</dd>
                  </div>
                  <div>
                    <dt className="text-gray-500">入札数</dt>
                    <dd className="text-xl font-bold">{selected.bid_count}</dd>
                  </div>
                  <div>
                    <dt className="text-gray-500">残り時間</dt>
                    <dd className="text-xl font-bold">{formatRemaining(selected.ends_at, nowMs)}</dd>
                  </div>
                  <div>
                    <dt className="text-gray-500">即決</dt>
                    <dd>{selected.buy_now_price != null ? formatYen(selected.buy_now_price) : '—'}</dd>
                  </div>
                </dl>

                {canManage && (
                  <div className="flex flex-wrap gap-2 mb-6">
                    <button type="button" onClick={() => runAction('start').catch(() => undefined)} className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-3 py-2 text-white text-sm">
                      <Play className="h-4 w-4" />開始
                    </button>
                    <button type="button" onClick={() => runAction('pause').catch(() => undefined)} className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-3 py-2 text-white text-sm">
                      <Pause className="h-4 w-4" />一時停止
                    </button>
                    <button type="button" onClick={() => runAction('resume').catch(() => undefined)} className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-white text-sm">
                      再開
                    </button>
                    <button type="button" onClick={() => runAction('finish').catch(() => undefined)} className="inline-flex items-center gap-2 rounded-lg bg-gray-700 px-3 py-2 text-white text-sm">
                      <Square className="h-4 w-4" />終了
                    </button>
                    <button type="button" onClick={() => runAction('cancel').catch(() => undefined)} className="inline-flex items-center gap-2 rounded-lg bg-gray-200 px-3 py-2 text-gray-800 text-sm dark:bg-gray-800 dark:text-gray-100">
                      <XCircle className="h-4 w-4" />キャンセル
                    </button>
                  </div>
                )}

                <h3 className="font-semibold mb-2 text-gray-900 dark:text-gray-100">入札履歴</h3>
                <ul className="space-y-2 max-h-64 overflow-y-auto">
                  {bids.map((b) => (
                    <li key={b.id} className="flex justify-between text-sm rounded-lg border px-3 py-2 dark:border-gray-800">
                      <span>user #{b.user_id}</span>
                      <span className="font-medium">{formatYen(b.amount)}</span>
                    </li>
                  ))}
                  {bids.length === 0 && <li className="text-sm text-gray-500">入札はありません</li>}
                </ul>
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
