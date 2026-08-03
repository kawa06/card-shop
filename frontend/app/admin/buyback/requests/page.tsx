'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Package, Search } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminBuybackApi } from '@/lib/api'
import { AdminBuybackRequestListItem } from '@/lib/types'
import { Input } from '@/components/ui/input'
import { BUYBACK_STATUS_FILTER_OPTIONS } from '@/lib/buyback-status-labels'

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('ja-JP')
}

function formatYen(value: number | null): string {
  if (value == null) return '—'
  return `¥${value.toLocaleString('ja-JP')}`
}

function isStoreRequest(item: AdminBuybackRequestListItem): boolean {
  return item.buyback_method === 'store' || item.buyback_method_label === '店舗買取'
}

function RequestTable({
  title,
  items,
  emptyText,
}: {
  title: string
  items: AdminBuybackRequestListItem[]
  emptyText: string
}) {
  const today = new Date().toISOString().slice(0, 10)
  return (
    <section className="mb-8">
      <h2 className="text-lg font-semibold text-gray-900 mb-3">
        {title}
        <span className="ml-2 text-sm font-normal text-gray-500">({items.length}件)</span>
      </h2>
      <div className="overflow-x-auto border rounded-lg">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-left">
            <tr>
              <th className="px-4 py-3">申込番号</th>
              <th className="px-4 py-3">会員</th>
              <th className="px-4 py-3">ステータス</th>
              <th className="px-4 py-3">本人確認</th>
              <th className="px-4 py-3">振込金額</th>
              <th className="px-4 py-3">振込</th>
              <th className="px-4 py-3">振込予定日</th>
              <th className="px-4 py-3">申込日時</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-6 text-center text-gray-500">
                  {emptyText}
                </td>
              </tr>
            ) : (
              items.map((item) => {
                const scheduledDate = item.payout_scheduled_at
                  ? new Date(item.payout_scheduled_at).toISOString().slice(0, 10)
                  : null
                const isDue =
                  scheduledDate &&
                  scheduledDate <= today &&
                  item.payout_transfer_status !== 'completed'
                return (
                  <tr
                    key={item.id}
                    className={`border-t ${isDue ? 'bg-amber-50' : ''}`}
                  >
                    <td className="px-4 py-3 font-mono text-xs">{item.request_number || `#${item.id}`}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium">{item.user_name}</div>
                      <div className="text-gray-500 text-xs">{item.user_email}</div>
                    </td>
                    <td className="px-4 py-3">{item.status_label}</td>
                    <td className="px-4 py-3">{item.identity_status_label || '—'}</td>
                    <td className="px-4 py-3">{formatYen(item.payout_total)}</td>
                    <td className="px-4 py-3">{item.payout_transfer_status_label || '—'}</td>
                    <td className="px-4 py-3">
                      {item.payout_scheduled_at ? formatDate(item.payout_scheduled_at) : '—'}
                      {isDue && (
                        <span className="ml-1 text-xs text-amber-700 font-medium">期限</span>
                      )}
                    </td>
                    <td className="px-4 py-3">{formatDate(item.submitted_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/admin/buyback/requests/${item.id}`}
                        className="text-yellow-600 hover:underline"
                      >
                        詳細
                      </Link>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default function AdminBuybackRequestsPage() {
  const { isReady } = useAdminGuard()
  const [items, setItems] = useState<AdminBuybackRequestListItem[]>([])
  const [searchInput, setSearchInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [payoutFilter, setPayoutFilter] = useState('')
  const [methodFilter, setMethodFilter] = useState('')
  const [identityFilter, setIdentityFilter] = useState(false)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isMounted, setIsMounted] = useState(false)

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
      } = {}
      if (searchQuery) params.q = searchQuery
      if (statusFilter) params.status = statusFilter
      if (methodFilter) params.buyback_method = methodFilter
      if (payoutFilter) params.payout_transfer_status = payoutFilter
      if (identityFilter) params.identity_not_approved = true
      if (dateFrom) params.date_from = `${dateFrom}T00:00:00`
      if (dateTo) params.date_to = `${dateTo}T23:59:59`
      const res = await adminBuybackApi.listRequests(params)
      setItems(res.data || [])
    } finally {
      setIsLoading(false)
    }
  }, [searchQuery, statusFilter, payoutFilter, methodFilter, identityFilter, dateFrom, dateTo])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void fetchAll()
  }, [isMounted, isReady, fetchAll])

  const mailItems = useMemo(
    () => items.filter((item) => !isStoreRequest(item)),
    [items],
  )
  const storeItems = useMemo(
    () => items.filter((item) => isStoreRequest(item)),
    [items],
  )

  if (!isMounted || !isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-6xl">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <Link href="/admin" className="text-gray-500 hover:text-gray-900">
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <Package className="h-6 w-6 text-yellow-400" />
            <h1 className="text-2xl font-bold text-gray-900">買取申請管理</h1>
          </div>
          <div className="flex gap-4 text-sm">
            <Link href="/admin/buyback/receiving" className="text-amber-700 hover:underline">
              荷物受付へ
            </Link>
            <Link href="/admin/buyback/shipping-verify" className="text-sky-700 hover:underline">
              発送前確認へ
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
          <select
            className="border rounded-md px-3 py-2 text-sm"
            value={methodFilter}
            onChange={(e) => setMethodFilter(e.target.value)}
          >
            <option value="">買取方法：すべて</option>
            <option value="mail">郵送買取</option>
            <option value="store">店舗買取</option>
          </select>
          <label className="flex items-center gap-2 text-sm border rounded-md px-3 py-2">
            <input
              type="checkbox"
              checked={identityFilter}
              onChange={(e) => setIdentityFilter(e.target.checked)}
            />
            本人確認未承認
          </label>
          <Input
            type="date"
            className="w-auto"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            title="申込日（開始）"
          />
          <Input
            type="date"
            className="w-auto"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            title="申込日（終了）"
          />
        </div>

        {isLoading ? (
          <p className="text-center text-gray-500 py-8">読み込み中...</p>
        ) : items.length === 0 ? (
          <p className="text-center text-gray-500 py-8">該当する申込はありません</p>
        ) : (
          <>
            <RequestTable title="郵送買取" items={mailItems} emptyText="郵送買取の申請はありません。" />
            <RequestTable title="店舗買取" items={storeItems} emptyText="店舗買取の申請はありません。" />
          </>
        )}
      </div>
    </div>
  )
}
