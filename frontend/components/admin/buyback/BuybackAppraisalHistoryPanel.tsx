'use client'

import { useCallback, useEffect, useState } from 'react'
import { adminBuybackApi } from '@/lib/api'
import { AdminBuybackAssessmentLog } from '@/lib/types'

function formatDate(value: string): string {
  return new Date(value).toLocaleString('ja-JP')
}

type Props = {
  requestId: number
  assessmentVersion?: number
}

export function BuybackAppraisalHistoryPanel({ requestId, assessmentVersion }: Props) {
  const [logs, setLogs] = useState<AdminBuybackAssessmentLog[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await adminBuybackApi.getAssessmentLogs(requestId)
      setLogs(res.data || [])
    } catch {
      setLogs([])
    } finally {
      setLoading(false)
    }
  }, [requestId])

  useEffect(() => {
    void load()
  }, [load, assessmentVersion])

  return (
    <div className="border rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold">査定履歴</h2>
        {assessmentVersion != null && assessmentVersion > 0 && (
          <span className="text-xs text-gray-500">版 {assessmentVersion}</span>
        )}
      </div>
      {loading ? (
        <p className="text-sm text-gray-500">読み込み中…</p>
      ) : logs.length === 0 ? (
        <p className="text-sm text-gray-500">査定履歴はまだありません</p>
      ) : (
        <ul className="space-y-2 text-sm max-h-64 overflow-y-auto">
          {logs.map((log) => (
            <li key={log.id} className="border-b pb-2">
              <div className="flex flex-wrap gap-x-2 gap-y-0.5">
                <span className="font-medium">{log.action_label}</span>
                {log.actor_name && <span className="text-gray-500">— {log.actor_name}</span>}
              </div>
              <div className="text-xs text-gray-500">{formatDate(log.created_at)}</div>
              {log.details?.assessed_total != null && (
                <div className="text-xs text-gray-600 mt-0.5">
                  査定合計: ¥{Number(log.details.assessed_total).toLocaleString('ja-JP')}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
