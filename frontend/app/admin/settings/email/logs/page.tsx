'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2, RefreshCw } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminEmailApi } from '@/lib/api'
import { toast } from '@/lib/use-toast'
import { Button } from '@/components/ui/button'

type LogItem = {
  id: number
  template_key?: string | null
  campaign_id?: number | null
  recipient: string
  subject: string
  status: string
  error_message?: string | null
  retry_count?: number
  created_at: string
}

type CampaignItem = {
  id: number
  template_key: string
  subject: string
  target_description?: string | null
  recipient_count: number
  success_count: number
  failed_count: number
  status: string
  send_mode: string
  scheduled_at?: string | null
  created_at: string
}

export default function AdminEmailLogsPage() {
  const { isReady } = useAdminGuard()
  const [logs, setLogs] = useState<LogItem[]>([])
  const [campaigns, setCampaigns] = useState<CampaignItem[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [tab, setTab] = useState<'logs' | 'campaigns'>('campaigns')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [logsRes, campRes] = await Promise.all([
        adminEmailApi.getSendLogs({ limit: 100, status: statusFilter || undefined }),
        adminEmailApi.listCampaigns(50),
      ])
      setLogs(logsRes.data)
      setCampaigns(campRes.data)
    } finally {
      setLoading(false)
    }
  }, [statusFilter])

  useEffect(() => {
    if (isReady) void load()
  }, [isReady, load])

  const handleRetryAll = async () => {
    try {
      const res = await adminEmailApi.retryAllFailed()
      toast({ title: res.data.message })
      void load()
    } catch {
      toast({ title: '再送に失敗しました', variant: 'destructive' })
    }
  }

  const handleRetryCampaign = async (id: number) => {
    try {
      const res = await adminEmailApi.retryCampaignFailed(id)
      toast({ title: res.data.message })
      void load()
    } catch {
      toast({ title: '再送に失敗しました', variant: 'destructive' })
    }
  }

  if (!isReady) return null

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      <Link href="/admin/settings/email" className="inline-flex items-center gap-2 text-gray-500 mb-4">
        <ArrowLeft className="h-4 w-4" /> メールテンプレート管理
      </Link>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">送信履歴</h1>
        <Button variant="outline" size="sm" onClick={handleRetryAll}>
          <RefreshCw className="h-4 w-4 mr-1" /> 失敗メールを再送
        </Button>
      </div>

      <div className="flex gap-2 mb-4">
        <button
          type="button"
          onClick={() => setTab('campaigns')}
          className={`px-3 py-1 rounded text-sm border ${tab === 'campaigns' ? 'bg-gray-900 text-white' : 'bg-white'}`}
        >
          配信キャンペーン
        </button>
        <button
          type="button"
          onClick={() => setTab('logs')}
          className={`px-3 py-1 rounded text-sm border ${tab === 'logs' ? 'bg-gray-900 text-white' : 'bg-white'}`}
        >
          個別ログ
        </button>
      </div>

      {loading ? (
        <Loader2 className="h-8 w-8 animate-spin mx-auto text-gray-400" />
      ) : tab === 'campaigns' ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="py-2 pr-4">日時</th>
                <th className="py-2 pr-4">件名</th>
                <th className="py-2 pr-4">対象</th>
                <th className="py-2 pr-4">成功/失敗</th>
                <th className="py-2 pr-4">状態</th>
                <th className="py-2 pr-4"></th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map((c) => (
                <tr key={c.id} className="border-b border-gray-100">
                  <td className="py-2 pr-4 whitespace-nowrap">
                    {new Date(c.created_at).toLocaleString('ja-JP')}
                  </td>
                  <td className="py-2 pr-4 max-w-[200px] truncate">{c.subject}</td>
                  <td className="py-2 pr-4">{c.target_description || '—'} ({c.recipient_count}人)</td>
                  <td className="py-2 pr-4">
                    <span className="text-green-700">{c.success_count}</span>
                    {' / '}
                    <span className="text-red-600">{c.failed_count}</span>
                  </td>
                  <td className="py-2 pr-4">{c.status}</td>
                  <td className="py-2 pr-4">
                    {c.failed_count > 0 && (
                      <Button variant="ghost" size="sm" onClick={() => handleRetryCampaign(c.id)}>
                        再送
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <>
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
                      <span className={log.status === 'failed' ? 'text-red-600' : 'text-green-700'}>
                        {log.status}
                        {log.retry_count ? ` (再送${log.retry_count}回)` : ''}
                      </span>
                      {log.error_message && (
                        <p className="text-xs text-red-500 truncate max-w-[240px]">{log.error_message}</p>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
