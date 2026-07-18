'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, MessageSquare, Search } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminInquiriesApi } from '@/lib/api'
import { AdminInquiryListItem, InquiryStats } from '@/lib/types'
import { inquiryCategoryLabel, inquiryStatusLabel, INQUIRY_CATEGORY_OPTIONS, INQUIRY_STATUS_COLORS } from '@/lib/inquiry-labels'
import { Input } from '@/components/ui/input'
import { InquiryCategorySelect } from '@/components/inquiries/InquiryCategorySelect'

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('ja-JP')
}

export default function AdminInquiriesPage() {
  const { isReady } = useAdminGuard()
  const [items, setItems] = useState<AdminInquiryListItem[]>([])
  const [stats, setStats] = useState<InquiryStats | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
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
      const params: { q?: string; status?: string; category?: string } = {}
      if (searchQuery) params.q = searchQuery
      if (statusFilter) params.status = statusFilter
      if (categoryFilter) params.category = categoryFilter
      const [listRes, statsRes] = await Promise.all([
        adminInquiriesApi.list(params),
        adminInquiriesApi.getStats(),
      ])
      setItems(listRes.data || [])
      setStats(statsRes.data)
    } finally {
      setIsLoading(false)
    }
  }, [searchQuery, statusFilter, categoryFilter])

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
            <MessageSquare className="h-6 w-6 text-yellow-400" />
            <h1 className="text-2xl font-bold text-gray-900">問い合わせ管理</h1>
          </div>
          <div className="flex gap-2 text-sm">
            <Link href="/admin/inquiries/templates" className="text-yellow-600 hover:underline">
              定型文管理
            </Link>
            <span className="text-gray-300">|</span>
            <Link href="/admin/settings/inquiries" className="text-yellow-600 hover:underline">
              設定
            </Link>
          </div>
        </div>

        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
            <StatCard label="未返信" value={stats.unreplied_count} highlight />
            <StatCard label="本日" value={stats.today_count} />
            <StatCard label="対応中" value={stats.in_progress_count} />
            <StatCard label="購入者待ち" value={stats.waiting_customer_count} />
            <StatCard label="解決済" value={stats.resolved_count} />
            <StatCard label="高優先" value={stats.high_priority_count} />
          </div>
        )}

        <div className="flex flex-wrap gap-3 mb-4">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              className="pl-9"
              placeholder="番号・件名・購入者名で検索"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
          </div>
          <select
            className="rounded-md border border-gray-200 px-3 py-2.5 text-base min-h-[44px] appearance-auto"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">すべてのステータス</option>
            {Object.entries(INQUIRY_STATUS_COLORS).map(([value]) => (
              <option key={value} value={value}>
                {inquiryStatusLabel(value)}
              </option>
            ))}
          </select>
          <div className="min-w-[180px]">
            <InquiryCategorySelect
              id="admin-inquiry-category-filter"
              value={categoryFilter}
              onChange={setCategoryFilter}
              options={INQUIRY_CATEGORY_OPTIONS}
              includeAllOption
              allOptionLabel="すべてのカテゴリ"
            />
          </div>
        </div>

        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-gray-50 rounded animate-pulse" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <p className="text-gray-500 text-sm">問い合わせがありません</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-gray-500">
                <tr>
                  <th className="p-3">番号</th>
                  <th className="p-3">件名</th>
                  <th className="p-3">購入者</th>
                  <th className="p-3">カテゴリ</th>
                  <th className="p-3">ステータス</th>
                  <th className="p-3">更新</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr
                    key={item.id}
                    className={`border-t border-gray-100 hover:bg-gray-50 ${
                      item.admin_unread_count > 0 ? 'bg-amber-50/50' : ''
                    }`}
                  >
                    <td className="p-3">
                      <Link href={`/admin/inquiries/${item.id}`} className="text-yellow-600 hover:underline font-mono text-xs">
                        {item.inquiry_number}
                        {item.admin_unread_count > 0 && (
                          <span className="ml-1 inline-block w-2 h-2 rounded-full bg-amber-500" />
                        )}
                      </Link>
                    </td>
                    <td className="p-3 max-w-[200px] truncate">{item.subject}</td>
                    <td className="p-3">
                      <div>{item.buyer_name || '—'}</div>
                      <div className="text-xs text-gray-400">{item.buyer_email}</div>
                    </td>
                    <td className="p-3 text-gray-600">{inquiryCategoryLabel(item.category)}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded border text-xs ${INQUIRY_STATUS_COLORS[item.status] || ''}`}>
                        {inquiryStatusLabel(item.status)}
                      </span>
                    </td>
                    <td className="p-3 text-gray-500 text-xs whitespace-nowrap">
                      {formatDate(item.last_message_at || item.updated_at || item.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  return (
    <div className={`rounded-lg border p-3 ${highlight ? 'border-amber-400/50 bg-amber-50/40' : 'border-gray-200 bg-gray-50'}`}>
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-2xl font-bold ${highlight ? 'text-amber-600' : 'text-gray-900'}`}>{value}</p>
    </div>
  )
}
