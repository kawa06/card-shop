'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, UserCheck, Search } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminBuybackApi } from '@/lib/api'
import { AdminIdentityListItem } from '@/lib/types'
import { Input } from '@/components/ui/input'

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('ja-JP')
}

const STATUS_OPTIONS = [
  { value: '', label: 'すべて' },
  { value: 'pending', label: '審査中' },
  { value: 'approved', label: '承認済み' },
  { value: 'rejected', label: '差戻し' },
]

export default function AdminBuybackKycPage() {
  const { isReady } = useAdminGuard()
  const [items, setItems] = useState<AdminIdentityListItem[]>([])
  const [searchInput, setSearchInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('pending')
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
      const res = await adminBuybackApi.listIdentity(params)
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
            <UserCheck className="h-6 w-6 text-yellow-400" />
            <h1 className="text-2xl font-bold text-gray-900">買取 KYC 審査</h1>
          </div>
          <Link href="/admin/buyback/requests" className="text-sm text-yellow-600 hover:underline">
            買取申込一覧へ
          </Link>
        </div>

        <div className="flex flex-wrap gap-3 mb-4">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              className="pl-9"
              placeholder="メール / 氏名で検索"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
          </div>
          <select
            className="border rounded-md px-3 py-2 text-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value || 'all'} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="overflow-x-auto border rounded-lg">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-left">
              <tr>
                <th className="px-4 py-3">会員</th>
                <th className="px-4 py-3">書類</th>
                <th className="px-4 py-3">ステータス</th>
                <th className="px-4 py-3">提出日時</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                    読み込み中...
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                    該当する本人確認はありません
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr key={item.id} className="border-t">
                    <td className="px-4 py-3">
                      <div className="font-medium">{item.user_name || '—'}</div>
                      <div className="text-gray-500 text-xs">{item.user_email}</div>
                    </td>
                    <td className="px-4 py-3">{item.document_type_label || '—'}</td>
                    <td className="px-4 py-3">{item.status_label}</td>
                    <td className="px-4 py-3">{formatDate(item.submitted_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/admin/buyback/kyc/${item.id}`}
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
