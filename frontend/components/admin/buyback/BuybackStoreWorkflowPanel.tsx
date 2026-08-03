'use client'

import { useState } from 'react'
import { AdminBuybackRequestDetail } from '@/lib/types'
import { adminBuybackApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('ja-JP')
}

type Props = {
  detail: AdminBuybackRequestDetail
  onUpdated: (detail: AdminBuybackRequestDetail) => void
  canEdit: boolean
}

export function BuybackStoreWorkflowPanel({ detail, onUpdated, canEdit }: Props) {
  const [estimateMinutes, setEstimateMinutes] = useState('30')
  const [estimateMessage, setEstimateMessage] = useState('')
  const [paymentMethod, setPaymentMethod] = useState('cash')
  const [paymentAmount, setPaymentAmount] = useState(
    detail.payout_total != null ? String(detail.payout_total) : detail.assessed_total != null ? String(detail.assessed_total) : ''
  )
  const [paymentNote, setPaymentNote] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  const run = async (key: string, fn: () => Promise<{ data: AdminBuybackRequestDetail }>) => {
    setBusy(key)
    setError('')
    try {
      const res = await fn()
      onUpdated(res.data)
    } catch {
      setError('操作に失敗しました')
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="border rounded-lg p-4 space-y-4 bg-violet-50/40 border-violet-200">
      <h2 className="font-semibold text-violet-900">店舗買取ワークフロー</h2>
      <div className="grid gap-2 text-sm sm:grid-cols-2">
        <p>
          <span className="text-gray-500">来店予定：</span>
          {formatDate(detail.store_visit_at)}
          {detail.store_visit_overdue && (
            <span className="ml-2 text-xs text-red-600 font-medium">来店遅延</span>
          )}
        </p>
        <p>
          <span className="text-gray-500">チェックイン：</span>
          {formatDate(detail.store_checked_in_at)}
        </p>
        <p>
          <span className="text-gray-500">査定開始：</span>
          {formatDate(detail.assessment_started_at)}
        </p>
        <p>
          <span className="text-gray-500">査定提示：</span>
          {formatDate(detail.assessment_presented_at)}
        </p>
      </div>

      {detail.latest_appraisal_estimate && (
        <div className="text-sm bg-white rounded-md border p-3">
          <p className="font-medium">査定待ち時間（通知済み）</p>
          <p>
            目安 {detail.latest_appraisal_estimate.estimated_minutes} 分
            {detail.latest_appraisal_estimate.message ? ` — ${detail.latest_appraisal_estimate.message}` : ''}
          </p>
        </div>
      )}

      {canEdit && (
        <div className="flex flex-wrap gap-2">
          {!detail.store_checked_in_at && (
            <Button
              size="sm"
              disabled={!!busy}
              onClick={() => void run('checkin', () => adminBuybackApi.storeCheckIn(detail.id))}
            >
              {busy === 'checkin' ? '処理中…' : '来店チェックイン'}
            </Button>
          )}
          {detail.store_checked_in_at && !detail.assessment_started_at && (
            <Button
              size="sm"
              disabled={!!busy}
              onClick={() => void run('start', () => adminBuybackApi.storeStartAssessment(detail.id))}
            >
              {busy === 'start' ? '処理中…' : '査定開始'}
            </Button>
          )}
        </div>
      )}

      {canEdit && detail.assessment_started_at && !detail.assessment_presented_at && (
        <div className="border-t pt-3 space-y-2">
          <p className="text-sm font-medium">査定待ち時間をお客様に通知</p>
          <div className="flex flex-wrap gap-2 items-end">
            <label className="text-sm">
              目安（分）
              <Input
                className="mt-1 w-24"
                type="number"
                min={1}
                value={estimateMinutes}
                onChange={(e) => setEstimateMinutes(e.target.value)}
              />
            </label>
            <label className="text-sm flex-1 min-w-[200px]">
              メッセージ
              <Input
                className="mt-1"
                placeholder="例: 混雑のため少しお待ちください"
                value={estimateMessage}
                onChange={(e) => setEstimateMessage(e.target.value)}
              />
            </label>
            <Button
              size="sm"
              disabled={!!busy}
              onClick={() =>
                void run('estimate', () =>
                  adminBuybackApi.storeAppraisalEstimate(detail.id, {
                    estimated_minutes: Math.max(1, Number(estimateMinutes) || 30),
                    message: estimateMessage || undefined,
                  })
                )
              }
            >
              通知する
            </Button>
          </div>
        </div>
      )}

      {canEdit && detail.status === 'accepted' && (
        <div className="border-t pt-3 space-y-2">
          <p className="text-sm font-medium">店舗でのお支払い</p>
          <div className="flex flex-wrap gap-2 items-end">
            <select
              className="border rounded-md px-2 py-2 text-sm"
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value)}
            >
              <option value="cash">現金</option>
              <option value="bank_transfer">銀行振込</option>
              <option value="paypay">PayPay</option>
            </select>
            <Input
              className="w-32"
              placeholder="支払金額"
              value={paymentAmount}
              onChange={(e) => setPaymentAmount(e.target.value)}
            />
            <Input
              className="flex-1 min-w-[160px]"
              placeholder="メモ"
              value={paymentNote}
              onChange={(e) => setPaymentNote(e.target.value)}
            />
            <Button
              size="sm"
              disabled={!!busy}
              onClick={() =>
                void run('pay', () =>
                  adminBuybackApi.storeCompletePayment(detail.id, {
                    payment_method: paymentMethod,
                    payment_amount: paymentAmount.trim() ? Number(paymentAmount) : undefined,
                    payment_note: paymentNote || undefined,
                  })
                )
              }
            >
              支払い完了
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!!busy}
              onClick={() => void run('complete', () => adminBuybackApi.storeCompleteTransaction(detail.id))}
            >
              取引完了
            </Button>
          </div>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  )
}
