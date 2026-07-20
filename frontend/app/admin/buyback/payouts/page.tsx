'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Banknote } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminBuybackApi } from '@/lib/api'
import { AdminBuybackRequestListItem } from '@/lib/types'

function formatYen(value: number | null): string {
  if (value == null) return '—'
  return `¥${value.toLocaleString('ja-JP')}`
}

export default function AdminBuybackPayoutsPage() {
  const { isReady } = useAdminGuard()
  const [items, setItems] = useState<AdminBuybackRequestListItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const fetchItems = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const res = await adminBuybackApi.listRequests({ status: 'payout_pending' })
      setItems(res.data)
    } catch {
      setError('振込待ち一覧の取得に失敗しました')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void fetchItems()
  }, [isMounted, isReady, fetchItems])

  if (!isMounted || !isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-5xl">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/admin" className="text-gray-500 hover:text-gray-900">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <Banknote className="h-6 w-6 text-emerald-500" />
          <h1 className="text-2xl font-bold text-gray-900">買取振込管理</h1>
        </div>

        <p className="text-sm text-gray-600 mb-4">
          振込準備中の申込です。振込後に「振込完了」を記録すると、お客様へ完了メールが送信されます。
        </p>

        {isLoading ? (
          <p className="text-gray-500">読み込み中...</p>
        ) : error ? (
          <p className="text-red-600">{error}</p>
        ) : items.length === 0 ? (
          <p className="text-gray-500">振込待ちの申込はありません</p>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left">申込番号</th>
                  <th className="px-4 py-2 text-left">会員</th>
                  <th className="px-4 py-2 text-right">振込予定</th>
                  <th className="px-4 py-2 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-t">
                    <td className="px-4 py-2">{item.request_number || `#${item.id}`}</td>
                    <td className="px-4 py-2">
                      {item.user_name}
                      <span className="text-gray-500 text-xs block">{item.user_email}</span>
                    </td>
                    <td className="px-4 py-2 text-right">{formatYen(item.payout_total)}</td>
                    <td className="px-4 py-2 text-right">
                      <Link
                        href={`/admin/buyback/requests/${item.id}`}
                        className="text-yellow-600 hover:underline"
                      >
                        振込処理
                      </Link>
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
