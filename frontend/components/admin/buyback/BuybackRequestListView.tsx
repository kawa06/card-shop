'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Package, Search } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminBuybackApi } from '@/lib/api'
import { AdminBuybackRequestListItem } from '@/lib/types'
import { Input } from '@/components/ui/input'
import { BUYBACK_STATUS_FILTER_OPTIONS } from '@/lib/buyback-status-labels'
import { BuybackChannel } from '@/components/admin/buyback/BuybackRequestDetailView'

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('ja-JP')
}

function formatYen(value: number | null): string {
  if (value == null) return '—'
  return `¥${value.toLocaleString('ja-JP')}`
}

type Props = {
  channel: BuybackChannel
}

export function BuybackRequestListView({ channel }: Props) {
  const { isReady } = useAdminGuard()
  const [items, setItems] = useState<AdminBuybackRequestListItem[]>([])
  const [searchInput, setSearchInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [payoutFilter, setPayoutFilter] = useState('')
  const [identityFilter, setIdentityFilter] = useState(false)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isMounted, setIsMounted] = useState(false)

  const channelLabel = channel === 'store' ? '店舗買取' : '郵送買取'
  const detailBase = channel === 'store' ? '/admin/buyback/store/requests' : '/admin/buyback/mail/requests'

  useEffect(() => {
    setIsMounted(true)
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => setSearchQuery(searchInput.trim()), 400)
    return () => window.clearTimeout(timer)
  }, [searchInput])

  const fetchAll = useCallback(async () => {
    setIsLoading(true)
    try {
      const params: {
        q?: string
        status?: string
        buyback_method?: string
        payout_transfer_status?: string
        identity_not_approved?: boolean
        date_from?: string
        date_to?: string
      } = {
        buyback_method: channel,
      }
      if (searchQuery) params.q = searchQuery
      if (statusFilter) params.status = statusFilter
      if (payoutFilter) params.payout_transfer_status = payoutFilter
      if (identityFilter) params.identity_not_approved = true
      if (dateFrom) params.date_from = `${dateFrom}T00:00:00`
      if (dateTo) params.date_to = `${dateTo}T23:59:59`
      const res = await adminBuybackApi.listRequests(params)
      setItems(res.data || [])
    } finally {
      setIsLoading(false)
    }
  }, [searchQuery, statusFilter, payoutFilter, identityFilter, dateFrom, dateTo, channel])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void fetchAll()
  }, [isMounted, isReady, fetchAll])

  if (!isMounted || !isReady) return null

  const today = new Date().toISOString().slice(0, 10)

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-6xl">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <Link href="/admin/buyback/requests" className="text-gray-500 hover:text-gray-900">
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <Package className={`h-6 w-6 ${channel === 'store' ? 'text-violet-500' : 'text-sky-500'}`} />
            <h1 className="text-2xl font-bold text-gray-900">{channelLabel} — 申込管理</h1>
          </div>
          <div className="flex gap-4 text-sm">
            {channel === 'mail' && (
              <>
                <Link href="/admin/buyback/receiving" className="text-amber-700 hover:underline">
                  荷物受付
                </Link>
                <Link href="/admin/buyback/shipping-verify" className="text-sky-700 hover:underline">
                  発送前確認
                </Link>
              </>
            )}
            {channel === 'store' && (
              <Link href="/admin/buyback/reservations" className="text-indigo-700 hover:underline">
                来店予約
              </Link>
            )}
            <Link
              href={channel === 'store' ? '/admin/buyback/mail/requests' : '/admin/buyback/store/requests'}
              className="text-gray-600 hover:underline"
            >
              {channel === 'store' ? '郵送買取へ' : '店舗買取へ'}
            </Link>
          </div>
        </div>

        <div className="flex flex-wrap gap-3 mb-4">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              className="pl-9"
              placeholder="申込番号 / メール / 氏名"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
          </div>
          <select
            className="border rounded-md px-3 py-2 text-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            {BUYBACK_STATUS_FILTER_OPTIONS.map((opt) => (
              <option key={opt.value || 'all'} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <select
            className="border rounded-md px-3 py-2 text-sm"
            value={payoutFilter}
            onChange={(e) => setPayoutFilter(e.target.value)}
          >
            <option value="">振込：すべて</option>
            <option value="unpaid">未振込</option>
            <option value="scheduled">振込予定</option>
            <option value="completed">振込済み</option>
          </select>
          <label className="flex items-center gap-2 text-sm border rounded-md px-3 py-2">
            <input type="checkbox" checked={identityFilter} onChange={(e) => setIdentityFilter(e.target.checked)} />
            本人確認未承認
          </label>
          <Input type="date" className="w-auto" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          <Input type="date" className="w-auto" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>

        {isLoading ? (
          <p className="text-center text-gray-500 py-8">読み込み中...</p>
        ) : items.length === 0 ? (
          <p className="text-center text-gray-500 py-8">{channelLabel}の申込はありません</p>
        ) : (
          <div className="overflow-x-auto border rounded-lg">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-left">
                <tr>
                  <th className="px-4 py-3">申込番号</th>
                  <th className="px-4 py-3">会員</th>
                  <th className="px-4 py-3">ステータス</th>
                  <th className="px-4 py-3">本人確認</th>
                  <th className="px-4 py-3">振込金額</th>
                  <th className="px-4 py-3">申込日時</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const scheduledDate = item.payout_scheduled_at
                    ? new Date(item.payout_scheduled_at).toISOString().slice(0, 10)
                    : null
                  const isDue =
                    scheduledDate &&
                    scheduledDate <= today &&
                    item.payout_transfer_status !== 'completed'
                  return (
                    <tr key={item.id} className={`border-t ${isDue ? 'bg-amber-50' : ''}`}>
                      <td className="px-4 py-3 font-mono text-xs">{item.request_number || `#${item.id}`}</td>
                      <td className="px-4 py-3">
                        <div className="font-medium">{item.user_name}</div>
                        <div className="text-gray-500 text-xs">{item.user_email}</div>
                      </td>
                      <td className="px-4 py-3">{item.status_label}</td>
                      <td className="px-4 py-3">{item.identity_status_label || '—'}</td>
                      <td className="px-4 py-3">{formatYen(item.payout_total)}</td>
                      <td className="px-4 py-3">{formatDate(item.submitted_at)}</td>
                      <td className="px-4 py-3 text-right">
                        <Link href={`${detailBase}/${item.id}`} className="text-yellow-600 hover:underline">
                          詳細
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
