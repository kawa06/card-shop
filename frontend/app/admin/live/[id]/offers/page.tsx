'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, HandCoins } from 'lucide-react'
import { useParams } from 'next/navigation'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminLiveApi, adminLiveOfferApi } from '@/lib/api'
import { getClerkSessionToken } from '@/lib/clerk-token'
import { useLiveEventSource } from '@/hooks/useLiveEventSource'
import type { LiveOffer, LiveOfferSettings, LiveStream } from '@/lib/types'

type StatusFilter = '' | 'pending' | 'accepted' | 'rejected' | 'held'

function formatYen(value: number): string {
  return `¥${value.toLocaleString('ja-JP')}`
}

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString('ja-JP')
}

export default function AdminLiveOffersPage() {
  const params = useParams<{ id: string }>()
  const streamId = Number(params.id)
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const canRead = hasPermission('offer.read')
  const canManage = hasPermission('offer.manage')
  const canReview = hasPermission('offer.review')

  const [stream, setStream] = useState<LiveStream | null>(null)
  const [settings, setSettings] = useState<LiveOfferSettings | null>(null)
  const [offers, setOffers] = useState<LiveOffer[]>([])
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('')

  const filtered = useMemo(() => {
    if (!statusFilter) return offers
    return offers.filter((o) => o.status === statusFilter)
  }, [offers, statusFilter])

  const reloadOffers = useCallback(async () => {
    const res = await adminLiveOfferApi.listOffers(streamId, { limit: 100 })
    setOffers(res.data.items)
  }, [streamId])

  const reload = useCallback(async () => {
    const [s, st] = await Promise.all([
      adminLiveApi.getStream(streamId),
      adminLiveOfferApi.getSettings(streamId),
    ])
    setStream(s.data)
    setSettings(st.data)
    await reloadOffers()
  }, [streamId, reloadOffers])

  useEffect(() => {
    if (!isReady || !canRead || !streamId) return
    reload().catch(() => undefined)
  }, [isReady, canRead, streamId, reload])

  useEffect(() => {
    if (!isReady || !canRead || !streamId) return
    const timer = window.setInterval(() => {
      reloadOffers().catch(() => undefined)
    }, 2000)
    return () => window.clearInterval(timer)
  }, [isReady, canRead, streamId, reloadOffers])

  const upsertOffer = useCallback((offer: LiveOffer) => {
    setOffers((prev) => {
      const idx = prev.findIndex((o) => o.id === offer.id)
      if (idx === -1) return [offer, ...prev]
      return prev.map((o) => (o.id === offer.id ? offer : o))
    })
  }, [])

  const getAuthHeaders = useCallback(async (): Promise<Record<string, string>> => {
    const token = await getClerkSessionToken()
    return token ? { Authorization: `Bearer ${token}` } : {}
  }, [])

  const onLiveEvent = useCallback(
    (evt: { type: string; payload: Record<string, unknown> }) => {
      if (evt.type.startsWith('offer.')) {
        upsertOffer(evt.payload as unknown as LiveOffer)
      }
    },
    [upsertOffer],
  )

  useLiveEventSource(
    isReady && canRead ? `/api/admin/live/streams/${streamId}/events` : null,
    onLiveEvent,
    { getAuthHeaders },
  )

  const toggleOffersEnabled = async () => {
    if (!settings || !canManage) return
    const res = await adminLiveOfferApi.patchSettings(streamId, {
      offers_enabled: !settings.offers_enabled,
    })
    setSettings(res.data)
  }

  const review = async (offer: LiveOffer, action: 'accept' | 'reject' | 'hold') => {
    if (!canReview) return
    let res
    if (action === 'accept') res = await adminLiveOfferApi.accept(streamId, offer.id)
    else if (action === 'reject') res = await adminLiveOfferApi.reject(streamId, offer.id)
    else res = await adminLiveOfferApi.hold(streamId, offer.id)
    upsertOffer(res.data)
  }

  if (!isReady || !canRead) return null
  if (!stream || !settings) return <div className="min-h-screen bg-white p-8">読み込み中...</div>

  return (
    <div className="min-h-screen bg-white dark:bg-gray-950">
      <div className="container py-8 max-w-6xl">
        <div className="flex flex-wrap items-center gap-3 mb-6">
          <Link href={`/admin/live/${streamId}`} className="text-gray-500 hover:text-gray-900 dark:hover:text-gray-100">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <HandCoins className="h-6 w-6 text-emerald-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">希望額管理</h1>
          <span className="text-sm text-gray-500">{stream.title}</span>
          <Link href={`/admin/live/${streamId}`} className="ml-auto text-sm text-emerald-700 hover:underline">
            配信に戻る
          </Link>
        </div>

        {canManage && (
          <div className="mb-6 flex flex-wrap items-center gap-3 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
            <span className="text-sm text-gray-600 dark:text-gray-300">配信の希望額受付</span>
            <button
              type="button"
              data-testid="offers-enabled-toggle"
              onClick={() => toggleOffersEnabled().catch(() => undefined)}
              className={`rounded-lg px-4 py-2 text-sm font-medium ${settings.offers_enabled ? 'bg-emerald-600 text-white' : 'bg-gray-200 text-gray-800 dark:bg-gray-800 dark:text-gray-100'}`}
            >
              {settings.offers_enabled ? 'ON' : 'OFF'}
            </button>
          </div>
        )}

        <div className="mb-4 flex flex-wrap gap-2 items-center">
          <label className="text-sm text-gray-600 dark:text-gray-300">
            ステータス
            <select
              data-testid="offer-status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
              className="ml-2 rounded-lg border px-3 py-2 text-sm dark:bg-gray-900 dark:border-gray-700"
            >
              <option value="">すべて</option>
              <option value="pending">pending</option>
              <option value="accepted">accepted</option>
              <option value="rejected">rejected</option>
              <option value="held">held</option>
            </select>
          </label>
          <button
            type="button"
            onClick={() => reloadOffers().catch(() => undefined)}
            className="text-sm text-gray-500 hover:underline"
          >
            再読み込み
          </button>
        </div>

        <ul className="space-y-3" data-testid="admin-offers-list">
          {filtered.map((offer) => (
            <li
              key={offer.id}
              data-testid={`admin-offer-${offer.id}`}
              className="rounded-xl border border-gray-200 dark:border-gray-800 p-4 flex flex-col sm:flex-row sm:items-center gap-3"
            >
              <div className="flex-1 min-w-0">
                <p className="font-medium text-gray-900 dark:text-gray-100">
                  #{offer.id} {formatYen(offer.amount)}
                  <span className="ml-2 text-sm font-normal text-gray-500">{offer.status}</span>
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-300 truncate">
                  {offer.sender_name || `user #${offer.user_id}`} ·{' '}
                  {offer.product?.card_name || `product #${offer.live_product_id}`}
                </p>
                <p className="text-xs text-gray-500">{formatWhen(offer.created_at)}</p>
              </div>
              {canReview && (offer.status === 'pending' || offer.status === 'held') && (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    data-testid={`offer-accept-${offer.id}`}
                    onClick={() => review(offer, 'accept').catch(() => undefined)}
                    className="rounded-lg bg-emerald-600 text-white px-3 py-2 text-sm"
                  >
                    承認
                  </button>
                  <button
                    type="button"
                    data-testid={`offer-hold-${offer.id}`}
                    onClick={() => review(offer, 'hold').catch(() => undefined)}
                    className="rounded-lg bg-amber-500 text-white px-3 py-2 text-sm"
                  >
                    保留
                  </button>
                  <button
                    type="button"
                    data-testid={`offer-reject-${offer.id}`}
                    onClick={() => review(offer, 'reject').catch(() => undefined)}
                    className="rounded-lg bg-gray-700 text-white px-3 py-2 text-sm"
                  >
                    却下
                  </button>
                </div>
              )}
            </li>
          ))}
          {filtered.length === 0 && <li className="text-sm text-gray-500">希望額はありません</li>}
        </ul>
      </div>
    </div>
  )
}
