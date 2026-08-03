'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Package } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminBuybackApi, adminBuybackLogisticsApi } from '@/lib/api'
import { AdminBuybackPackage, AdminBuybackRequestDetail } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { buybackStatusLabel } from '@/lib/buyback-status-labels'
import {
  BuybackAssessmentTable,
  ItemDraft,
  itemToDraft,
} from '@/components/admin/buyback/BuybackAssessmentTable'
import { BuybackStoreWorkflowPanel } from '@/components/admin/buyback/BuybackStoreWorkflowPanel'
import { BuybackMailWorkflowPanel } from '@/components/admin/buyback/BuybackMailWorkflowPanel'
import { BuybackAppraisalHistoryPanel } from '@/components/admin/buyback/BuybackAppraisalHistoryPanel'

export type BuybackChannel = 'mail' | 'store'

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('ja-JP')
}

function formatYen(value: number | null): string {
  if (value == null) return '—'
  return `¥${value.toLocaleString('ja-JP')}`
}

function draftsFromDetail(detail: AdminBuybackRequestDetail): Record<number, ItemDraft> {
  const out: Record<number, ItemDraft> = {}
  detail.items.forEach((item) => {
    out[item.id] = itemToDraft(item)
  })
  return out
}

type Props = {
  id: number
  channel: BuybackChannel
}

export function BuybackRequestDetailView({ id, channel }: Props) {
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const [detail, setDetail] = useState<AdminBuybackRequestDetail | null>(null)
  const [itemDrafts, setItemDrafts] = useState<Record<number, ItemDraft>>({})
  const [nextStatus, setNextStatus] = useState('')
  const [adminNote, setAdminNote] = useState('')
  const [trackingNumber, setTrackingNumber] = useState('')
  const [assessedTotal, setAssessedTotal] = useState('')
  const [customerStatusNote, setCustomerStatusNote] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [sendEmail, setSendEmail] = useState(true)
  const [forceEmail, setForceEmail] = useState(false)
  const [isSavingItems, setIsSavingItems] = useState(false)
  const [isPresenting, setIsPresenting] = useState(false)
  const [error, setError] = useState('')
  const [isMounted, setIsMounted] = useState(false)
  const [packages, setPackages] = useState<AdminBuybackPackage[]>([])
  const [packageBoxes, setPackageBoxes] = useState('1')
  const [packageKind, setPackageKind] = useState('return')
  const [packageTimeSlot, setPackageTimeSlot] = useState('')
  const [isIssuingPackages, setIsIssuingPackages] = useState(false)
  const [packageError, setPackageError] = useState('')

  const listHref = channel === 'store' ? '/admin/buyback/store/requests' : '/admin/buyback/mail/requests'
  const channelLabel = channel === 'store' ? '店舗買取' : '郵送買取'
  const isStore = channel === 'store'

  const canIssuePackages =
    hasPermission('buyback.package.write') &&
    detail &&
    !isStore &&
    ['assessed', 'awaiting_customer', 'accepted', 'rejected'].includes(detail.status)
  const canAssess = hasPermission('buyback.assessment.write')

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const fetchDetail = useCallback(async () => {
    if (!id || Number.isNaN(id)) return
    setIsLoading(true)
    setError('')
    try {
      const res = await adminBuybackApi.getRequest(id)
      setDetail(res.data)
      setItemDrafts(draftsFromDetail(res.data))
      setAdminNote(res.data.admin_note || '')
      setTrackingNumber(res.data.tracking_number || '')
      setCustomerStatusNote(res.data.customer_status_note || '')
      setAssessedTotal(res.data.assessed_total != null ? String(res.data.assessed_total) : '')
      setNextStatus(res.data.allowed_next_statuses[0] || '')
    } catch {
      setError('申込情報の取得に失敗しました')
    } finally {
      setIsLoading(false)
    }
  }, [id])

  const fetchPackages = useCallback(async () => {
    if (!id || Number.isNaN(id) || !hasPermission('buyback.package.read') || isStore) {
      setPackages([])
      return
    }
    try {
      const res = await adminBuybackLogisticsApi.listPackages(id)
      setPackages(res.data || [])
    } catch {
      setPackages([])
    }
  }, [id, hasPermission, isStore])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void fetchDetail()
    void fetchPackages()
  }, [isMounted, isReady, fetchDetail, fetchPackages])

  const handleIssuePackages = async (replace = false) => {
    if (!detail) return
    setIsIssuingPackages(true)
    setPackageError('')
    try {
      const res = await adminBuybackLogisticsApi.issuePackages(detail.id, {
        total_boxes: Math.max(1, Number(packageBoxes) || 1),
        package_kind: packageKind,
        preferred_time_slot: packageTimeSlot || undefined,
        replace_existing: replace,
      })
      setPackages(res.data || [])
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        '梱包バーコードの発行に失敗しました'
      setPackageError(String(msg))
    } finally {
      setIsIssuingPackages(false)
    }
  }

  const handleCompletePackage = async (packageId: number) => {
    setPackageError('')
    try {
      await adminBuybackLogisticsApi.completePackage(packageId)
      await fetchPackages()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        '梱包完了に失敗しました'
      setPackageError(String(msg))
    }
  }

  const updateItemDraft = (itemId: number, patch: Partial<ItemDraft>) => {
    setItemDrafts((prev) => ({
      ...prev,
      [itemId]: { ...prev[itemId], ...patch },
    }))
  }

  const handleSaveItems = async () => {
    if (!detail) return
    setIsSavingItems(true)
    setError('')
    try {
      const payload = {
        items: detail.items.map((item) => {
          const draft = itemDrafts[item.id]
          return {
            id: item.id,
            line_status: draft.line_status,
            condition_code: draft.condition_code,
            assessed_unit_price: draft.assessed_unit_price.trim()
              ? Number(draft.assessed_unit_price)
              : null,
            rejection_reason_code: draft.rejection_reason_code || null,
            rejection_reason_text: draft.rejection_reason_text.trim() || null,
            assessment_comment: draft.assessment_comment.trim() || null,
            is_return_target: draft.is_return_target,
            is_disposal_target: draft.is_disposal_target,
          }
        }),
        recalculate_assessed_total: true,
        apply_handling_policy: true,
      }
      const res = await adminBuybackApi.updateRequestItems(detail.id, payload)
      setDetail(res.data)
      setItemDrafts(draftsFromDetail(res.data))
      setAssessedTotal(res.data.assessed_total != null ? String(res.data.assessed_total) : '')
    } catch {
      setError('商品査定の保存に失敗しました（理由・単価を確認してください）')
    } finally {
      setIsSavingItems(false)
    }
  }

  const handlePresentAssessment = async () => {
    if (!detail) return
    setIsPresenting(true)
    setError('')
    try {
      const res = await adminBuybackApi.presentAssessment(detail.id, {
        customer_status_note: customerStatusNote.trim() || undefined,
      })
      setDetail(res.data)
      setCustomerStatusNote(res.data.customer_status_note || '')
    } catch {
      setError('査定結果の提示に失敗しました')
    } finally {
      setIsPresenting(false)
    }
  }

  const handleUpdate = async () => {
    if (!detail || !nextStatus) return
    setIsSaving(true)
    setError('')
    try {
      const payload: {
        status: string
        admin_note?: string
        tracking_number?: string
        assessed_total?: number
        send_email?: boolean
        force_email?: boolean
      } = {
        status: nextStatus,
        admin_note: adminNote,
        tracking_number: trackingNumber,
        send_email: sendEmail,
        force_email: forceEmail,
      }
      if (assessedTotal.trim()) payload.assessed_total = Number(assessedTotal)
      const res = await adminBuybackApi.updateRequest(detail.id, payload)
      setDetail(res.data)
      setNextStatus(res.data.allowed_next_statuses[0] || '')
    } catch {
      setError('ステータス更新に失敗しました')
    } finally {
      setIsSaving(false)
    }
  }

  if (!isMounted || !isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-6xl">
        <div className="flex items-center gap-3 mb-6">
          <Link href={listHref} className="text-gray-500 hover:text-gray-900">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <Package className="h-6 w-6 text-yellow-400" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{channelLabel} — 申込詳細</h1>
            <p className="text-sm text-gray-500">#{detail?.request_number || id}</p>
          </div>
        </div>

        {isLoading ? (
          <p className="text-gray-500">読み込み中...</p>
        ) : !detail ? (
          <p className="text-red-600">{error || 'データが見つかりません'}</p>
        ) : (
          <div className="space-y-6">
            {isStore ? (
              <BuybackStoreWorkflowPanel
                detail={detail}
                onUpdated={setDetail}
                canEdit={canAssess}
              />
            ) : (
              <BuybackMailWorkflowPanel detail={detail} />
            )}

            <div className="border rounded-lg p-4 space-y-2 text-sm">
              <p>
                <span className="text-gray-500">申込番号：</span>
                {detail.request_number || `#${detail.id}`}
              </p>
              <p>
                <span className="text-gray-500">会員：</span>
                {detail.user_name}（{detail.user_email}）
              </p>
              <p>
                <span className="text-gray-500">ステータス：</span>
                {buybackStatusLabel(detail.status, detail.status_label)}
              </p>
              <p>
                <span className="text-gray-500">見積 / 査定 / 振込：</span>
                {formatYen(detail.estimated_total)} / {formatYen(detail.assessed_total)} /{' '}
                {formatYen(detail.payout_total)}
              </p>
              {detail.customer_note && (
                <p>
                  <span className="text-gray-500">お客様メモ：</span>
                  {detail.customer_note}
                </p>
              )}
            </div>

            <BuybackAssessmentTable
              items={detail.items}
              drafts={itemDrafts}
              canEdit={canAssess}
              reasonOptions={detail.rejection_reason_options || []}
              conditionOptions={detail.condition_code_options || []}
              onChange={updateItemDraft}
              onSave={() => void handleSaveItems()}
              isSaving={isSavingItems}
            />

            {canAssess && ['assessing', 'assessed', 'received'].includes(detail.status) && (
              <div className="border rounded-lg p-4 space-y-3 bg-amber-50/50">
                <h2 className="font-semibold">査定結果をお客様に提示</h2>
                <textarea
                  className="w-full border rounded-md px-3 py-2 text-sm min-h-[80px]"
                  placeholder="お客様向けメッセージ（任意）"
                  value={customerStatusNote}
                  onChange={(e) => setCustomerStatusNote(e.target.value)}
                />
                <Button onClick={() => void handlePresentAssessment()} disabled={isPresenting}>
                  {isPresenting ? '送信中…' : '査定結果を提示する'}
                </Button>
              </div>
            )}

            <BuybackAppraisalHistoryPanel
              requestId={detail.id}
              assessmentVersion={detail.assessment_result_version}
            />

            {(canIssuePackages || packages.length > 0) && (
              <div className="border rounded-lg p-4 space-y-3">
                <h2 className="font-semibold">梱包バーコード（返送）</h2>
                {canIssuePackages && (
                  <div className="flex flex-wrap gap-3 items-end">
                    <label className="text-sm">
                      箱数
                      <Input
                        className="mt-1 w-24"
                        type="number"
                        min={1}
                        max={50}
                        value={packageBoxes}
                        onChange={(e) => setPackageBoxes(e.target.value)}
                      />
                    </label>
                    <Button onClick={() => void handleIssuePackages(false)} disabled={isIssuingPackages}>
                      梱包用バーコードを発行
                    </Button>
                  </div>
                )}
                {packageError && <p className="text-sm text-red-600">{packageError}</p>}
                {packages.length > 0 && (
                  <div className="overflow-x-auto border rounded-md">
                    <table className="min-w-full text-sm">
                      <tbody>
                        {packages.map((pkg) => (
                          <tr key={pkg.id} className="border-t">
                            <td className="px-3 py-2 font-mono text-xs">{pkg.package_code}</td>
                            <td className="px-3 py-2">
                              {hasPermission('buyback.package.write') && pkg.status === 'packing' && (
                                <Button size="sm" variant="outline" onClick={() => void handleCompletePackage(pkg.id)}>
                                  梱包完了
                                </Button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {detail.allowed_next_statuses.length > 0 && (
              <div className="border rounded-lg p-4 space-y-3">
                <h2 className="font-semibold">ステータス更新</h2>
                <select
                  className="border rounded-md px-3 py-2 text-sm w-full"
                  value={nextStatus}
                  onChange={(e) => setNextStatus(e.target.value)}
                >
                  {(detail.allowed_next_status_labels || []).map((opt) => (
                    <option key={opt.code} value={opt.code}>
                      {buybackStatusLabel(opt.code, opt.label)}
                    </option>
                  ))}
                </select>
                {!isStore && (
                  <Input placeholder="追跡番号" value={trackingNumber} onChange={(e) => setTrackingNumber(e.target.value)} />
                )}
                <Input placeholder="管理者メモ" value={adminNote} onChange={(e) => setAdminNote(e.target.value)} />
                {error && <p className="text-sm text-red-600">{error}</p>}
                <Button onClick={() => void handleUpdate()} disabled={isSaving || !nextStatus}>
                  更新する
                </Button>
              </div>
            )}

            {detail.status_history.length > 0 && (
              <div className="border rounded-lg p-4">
                <h2 className="font-semibold mb-3">ステータス履歴</h2>
                <ul className="space-y-2 text-sm">
                  {detail.status_history.map((h) => (
                    <li key={h.id} className="border-b pb-2">
                      {formatDate(h.created_at)} —{' '}
                      {h.from_status_label ? `${h.from_status_label} → ` : ''}
                      {h.to_status_label}
                      {h.note ? `（${h.note}）` : ''}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
