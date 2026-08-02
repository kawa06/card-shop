'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminEmailApi } from '@/lib/api'

type LogItem = {
  id: number
  template_key?: string | null
  recipient: string
  subject: string
  status: string
  error_message?: string | null
  created_at: string
}

export default function AdminEmailLogsPage() {
  const { isReady } = useAdminGuard()
  const [logs, setLogs] = useState<LogItem[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await adminEmailApi.getSendLogs({
        limit: 100,
        status: statusFilter || undefined,
      })
      setLogs(res.data)
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => {
    if (isReady) void load()
  }, [isReady, load])

  if (!isReady) return null

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      <Link href="/admin/settings/email" className="inline-flex items-center gap-2 text-gray-500 mb-4">
        <ArrowLeft className="h-4 w-4" /> メール管理
      </Link>
      <h1 className="text-2xl font-bold mb-4">送信履歴</h1>

      <div className="flex gap-2 mb-4">
        {['', 'sent', 'failed', 'skipped'].map((s) => (
          <button
            key={s || 'all'}
            type="button"
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1 rounded text-sm border ${
              statusFilter === s ? 'bg-gray-900 text-white' : 'bg-white'
            }`}
          >
            {s || 'すべて'}
          </button>
        ))}
      </div>

      {loading ? (
        <Loader2 className="h-8 w-8 animate-spin mx-auto text-gray-400" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="py-2 pr-4">日時</th>
                <th className="py-2 pr-4">テンプレート</th>
                <th className="py-2 pr-4">宛先</th>
                <th className="py-2 pr-4">状態</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-gray-100">
                  <td className="py-2 pr-4 whitespace-nowrap">
                    {new Date(log.created_at).toLocaleString('ja-JP')}
                  </td>
                  <td className="py-2 pr-4">{log.template_key || '—'}</td>
                  <td className="py-2 pr-4">{log.recipient}</td>
                  <td className="py-2 pr-4">
                    <span
                      className={
                        log.status === 'failed' ? 'text-red-600' : 'text-green-700'
                      }
                    >
                      {log.status}
                    </span>
                    {log.error_message && (
                      <p className="text-xs text-red-500 truncate max-w-[200px]">{log.error_message}</p>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
