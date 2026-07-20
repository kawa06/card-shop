'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminSecurityApi } from '@/lib/api'
import type { AdminAuditLog } from '@/lib/types'
import { AdminSecurityNav } from '@/components/admin/AdminSecurityNav'
import { toast } from '@/lib/use-toast'

export default function AdminSecurityAuditLogDetailPage() {
  const params = useParams()
  const id = Number(params.id)
  const { isReady } = useAdminGuard()
  const [log, setLog] = useState<AdminAuditLog | null>(null)

  useEffect(() => {
    if (!isReady || !id) return
    adminSecurityApi
      .getAuditLog(id)
      .then((res) => setLog(res.data))
      .catch(() => toast({ title: '監査ログの取得に失敗しました', variant: 'destructive' }))
  }, [isReady, id])

  if (!isReady || !log) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-3xl">
        <AdminSecurityNav title="監査ログ詳細" />
        <dl className="space-y-4 rounded-xl border border-gray-200 p-6 text-sm">
          <div>
            <dt className="text-gray-500">操作</dt>
            <dd className="font-mono">{log.action}</dd>
          </div>
          <div>
            <dt className="text-gray-500">結果</dt>
            <dd>{log.result}</dd>
          </div>
          <div>
            <dt className="text-gray-500">実行者</dt>
            <dd>{log.actor_email || '—'}</dd>
          </div>
          <div>
            <dt className="text-gray-500">リソース</dt>
            <dd>
              {log.resource_type || '—'} / {log.resource_id || '—'}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">IPアドレス</dt>
            <dd>{log.ip_address || '（取得不可 — プロキシ経由または TestClient）'}</dd>
          </div>
          <div>
            <dt className="text-gray-500">User-Agent</dt>
            <dd className="break-all">{log.user_agent || '（取得不可 — リクエストヘッダなし）'}</dd>
          </div>
          <div>
            <dt className="text-gray-500">理由</dt>
            <dd>{log.reason || '—'}</dd>
          </div>
          <div>
            <dt className="text-gray-500">変更前</dt>
            <dd className="whitespace-pre-wrap break-all font-mono text-xs bg-gray-50 p-2 rounded">
              {log.before_data || '—'}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">変更後</dt>
            <dd className="whitespace-pre-wrap break-all font-mono text-xs bg-gray-50 p-2 rounded">
              {log.after_data || '—'}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">日時</dt>
            <dd>{new Date(log.created_at).toLocaleString('ja-JP')}</dd>
          </div>
        </dl>
      </div>
    </div>
  )
}
