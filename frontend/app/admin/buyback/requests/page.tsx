'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Package, Search } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminBuybackApi } from '@/lib/api'
import { AdminBuybackRequestListItem } from '@/lib/types'
import { Input } from '@/components/ui/input'

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('ja-JP')
}

function formatYen(value: number | null): string {
  if (value == null) return '—'
  return `¥${value.toLocaleString('ja-JP')}`
}

export default function AdminBuybackRequestsPage() {
  const { isReady } = useAdminGuard()
  const [items, setItems] = useState<AdminBuybackRequestListItem[]>([])
  const [searchInput, setSearchInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('submitted')
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
      const params: { q?: string; status?: string } = {}
      if (searchQuery) params.q = searchQuery
      if (statusFilter) params.status = statusFilter
      const res = await adminBuybackApi.listRequests(params)
      setItems(res.data || [])
    } finally {
      setIsLoading(false)
    }
  }, [searchQuery, statusFilter])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void fetchAll()
  }, [isMounted, isReady, fetchAll])

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
            <h1 className="text-2xl font-bold text-gray-900">買取申込管理</h1>
          </div>
          <div className="flex gap-4 text-sm">
            <Link href="/admin/buyback/payouts" className="text-emerald-600 hover:underline">
              振込管理へ
            </Link>
            <Link href="/admin/buyback/kyc" className="text-yellow-600 hover:underline">
              KYC 審査へ
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
            <option value="">すべて</option>
            <option value="submitted">申込受付</option>
            <option value="received">商品到着</option>
            <option value="assessing">査定中</option>
            <option value="assessed">査定完了</option>
            <option value="payout_pending">振込準備中</option>
            <option value="paid">振込完了</option>
          </select>
        </div>

        <div className="overflow-x-auto border rounded-lg">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-left">
              <tr>
                <th className="px-4 py-3">申込番号</th>
                <th className="px-4 py-3">会員</th>
                <th className="px-4 py-3">ステータス</th>
                <th className="px-4 py-3">見積</th>
                <th className="px-4 py-3">申込日時</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                    読み込み中...
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                    該当する申込はありません
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr key={item.id} className="border-t">
                    <td className="px-4 py-3 font-mono text-xs">{item.request_number || `#${item.id}`}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium">{item.user_name}</div>
                      <div className="text-gray-500 text-xs">{item.user_email}</div>
                    </td>
                    <td className="px-4 py-3">{item.status_label}</td>
                    <td className="px-4 py-3">{formatYen(item.estimated_total)}</td>
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
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
