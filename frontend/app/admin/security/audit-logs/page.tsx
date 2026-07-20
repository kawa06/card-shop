'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminSecurityApi } from '@/lib/api'
import type { AdminAuditLog } from '@/lib/types'
import { AdminSecurityNav } from '@/components/admin/AdminSecurityNav'
import { toast } from '@/lib/use-toast'

export default function AdminSecurityAuditLogsPage() {
  const { isReady } = useAdminGuard()
  const [items, setItems] = useState<AdminAuditLog[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isReady) return
    adminSecurityApi
      .listAuditLogs({ per_page: 50 })
      .then((res) => setItems(res.data.items))
      .catch(() => toast({ title: '監査ログの取得に失敗しました', variant: 'destructive' }))
      .finally(() => setLoading(false))
  }, [isReady])

  if (!isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-6xl">
        <AdminSecurityNav title="監査ログ一覧" />
        <div className="rounded-xl border border-gray-200 overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-gray-400 animate-pulse">読み込み中...</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b border-gray-200 bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-gray-500">日時</th>
                  <th className="px-4 py-3 text-left text-gray-500">操作</th>
                  <th className="px-4 py-3 text-left text-gray-500">実行者</th>
                  <th className="px-4 py-3 text-left text-gray-500">結果</th>
                  <th className="px-4 py-3 text-left text-gray-500">詳細</th>
                </tr>
              </thead>
              <tbody>
                {items.map((log) => (
                  <tr key={log.id} className="border-b border-gray-100">
                    <td className="px-4 py-3 whitespace-nowrap text-gray-500">
                      {new Date(log.created_at).toLocaleString('ja-JP')}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">{log.action}</td>
                    <td className="px-4 py-3">{log.actor_email || '—'}</td>
                    <td className="px-4 py-3">{log.result}</td>
                    <td className="px-4 py-3">
                      <Link href={`/admin/security/audit-logs/${log.id}`} className="text-yellow-600 hover:underline">
                        詳細
                      </Link>
                    </td>
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
