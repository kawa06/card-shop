'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminBuybackLogisticsApi } from '@/lib/api'
import type { AdminBuybackLogisticsLog } from '@/lib/types'
import { Button } from '@/components/ui/button'

const TYPE_LABELS: Record<string, string> = {
  scan: 'スキャン',
  print: '印刷',
  audit: '監査',
}

export default function AdminBuybackLogisticsLogsPage() {
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const [items, setItems] = useState<AdminBuybackLogisticsLog[]>([])
  const [logType, setLogType] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [total, setTotal] = useState(0)

  useEffect(() => {
    if (!isReady) return
    if (!hasPermission('buyback.logs.read')) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    adminBuybackLogisticsApi
      .listLogisticsLogs({ log_type: logType === 'all' ? undefined : logType, per_page: 50 })
      .then((res) => {
        setItems(res.data.items)
        setTotal(res.data.total)
      })
      .catch(() => setError('物流ログの取得に失敗しました'))
      .finally(() => setLoading(false))
  }, [hasPermission, isReady, logType])

  if (!isReady) return null

  if (!hasPermission('buyback.logs.read')) {
    return (
      <div className="p-8">
        <p className="text-red-600">物流ログの閲覧権限がありません。</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-6 max-w-6xl space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link href="/admin" className="text-gray-500 hover:text-gray-800">
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div>
              <h1 className="text-xl font-semibold">買取物流ログ</h1>
              <p className="text-sm text-gray-500">スキャン・印刷・監査（計 {total} 件）</p>
            </div>
          </div>
          <div className="flex gap-2">
            {(['all', 'scan', 'print', 'audit'] as const).map((key) => (
              <Button
                key={key}
                size="sm"
                variant={logType === key ? 'default' : 'outline'}
                onClick={() => setLogType(key)}
              >
                {key === 'all' ? 'すべて' : TYPE_LABELS[key]}
              </Button>
            ))}
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="rounded-xl border overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-gray-400 animate-pulse">読み込み中...</div>
          ) : items.length === 0 ? (
            <div className="p-8 text-center text-gray-400">ログがありません</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b text-left text-gray-500">
                <tr>
                  <th className="px-3 py-2">日時</th>
                  <th className="px-3 py-2">種別</th>
                  <th className="px-3 py-2">操作</th>
                  <th className="px-3 py-2">実行者</th>
                  <th className="px-3 py-2">対象</th>
                  <th className="px-3 py-2">結果</th>
                </tr>
              </thead>
              <tbody>
                {items.map((log) => (
                  <tr key={log.id} className="border-b border-gray-100">
                    <td className="px-3 py-2 whitespace-nowrap text-gray-500">
                      {log.created_at ? new Date(log.created_at).toLocaleString('ja-JP') : '—'}
                    </td>
                    <td className="px-3 py-2">{TYPE_LABELS[log.log_type] || log.log_type}</td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {log.action}
                      {log.includes_pii ? (
                        <span className="ml-1 text-amber-700">PII</span>
                      ) : null}
                      {log.is_reprint ? (
                        <span className="ml-1 text-red-600">再印刷</span>
                      ) : null}
                    </td>
                    <td className="px-3 py-2">{log.actor_name || '—'}</td>
                    <td className="px-3 py-2 text-xs text-gray-600">
                      {log.request_id ? (
                        <Link
                          href={`/admin/buyback/requests/${log.request_id}`}
                          className="text-sky-700 hover:underline"
                        >
                          申込#{log.request_id}
                        </Link>
                      ) : null}
                      {log.package_id ? ` 梱包#${log.package_id}` : ''}
                    </td>
                    <td className="px-3 py-2">{log.result || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
