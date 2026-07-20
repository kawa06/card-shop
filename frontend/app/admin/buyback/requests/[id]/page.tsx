'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { ArrowLeft, Package } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminBuybackApi, adminBuybackLogisticsApi } from '@/lib/api'
import {
  AdminBuybackPackage,
  AdminBuybackRequestDetail,
  AdminBuybackRequestItem,
} from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const STATUS_LABELS: Record<string, string> = {
  submitted: '申込受付',
  received: '商品到着',
  assessing: '査定中',
  assessed: '査定完了',
  awaiting_customer: 'ご確認待ち',
  accepted: '買取成立',
  rejected: '買取不可',
  payout_pending: '振込準備中',
  paid: '振込完了',
  returned: '返送',
  cancelled: 'キャンセル',
}

const LINE_STATUS_OPTIONS = [
  { value: 'pending', label: '査定待ち' },
  { value: 'buyable', label: '買取可能' },
  { value: 'reduced', label: '減額買取' },
  { value: 'rejected', label: '買取不可' },
]

const RETURN_STATUS_OPTIONS = [
  { value: 'none', label: '—' },
  { value: 'pending', label: '返送準備中' },
  { value: 'shipped', label: '返送済み' },
  { value: 'completed', label: '返送完了' },
]

type ItemDraft = {
  line_status: string
  assessed_unit_price: string
  accepted_unit_price: string
  rejection_reason_code: string
  rejection_reason_text: string
  is_return_target: boolean
  is_disposal_target: boolean
  return_status: string
  return_tracking_number: string
  return_shipping_cost: string
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('ja-JP')
}

function formatYen(value: number | null): string {
  if (value == null) return '—'
  return `¥${value.toLocaleString('ja-JP')}`
}

function itemToDraft(item: AdminBuybackRequestItem): ItemDraft {
  return {
    line_status: item.line_status || 'pending',
    assessed_unit_price: item.assessed_unit_price != null ? String(item.assessed_unit_price) : '',
    accepted_unit_price: item.accepted_unit_price != null ? String(item.accepted_unit_price) : '',
    rejection_reason_code: item.rejection_reason_code || '',
    rejection_reason_text: item.rejection_reason_text || '',
    is_return_target: Boolean(item.is_return_target),
    is_disposal_target: Boolean(item.is_disposal_target),
    return_status: item.return_status || 'none',
    return_tracking_number: item.return_tracking_number || '',
    return_shipping_cost:
      item.return_shipping_cost != null ? String(item.return_shipping_cost) : '',
  }
}

function draftsFromDetail(detail: AdminBuybackRequestDetail): Record<number, ItemDraft> {
  const out: Record<number, ItemDraft> = {}
  detail.items.forEach((item) => {
    out[item.id] = itemToDraft(item)
  })
  return out
}

export default function AdminBuybackRequestDetailPage() {
  const params = useParams()
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const id = Number(params.id)
  const [detail, setDetail] = useState<AdminBuybackRequestDetail | null>(null)
  const [itemDrafts, setItemDrafts] = useState<Record<number, ItemDraft>>({})
  const [nextStatus, setNextStatus] = useState('')
  const [adminNote, setAdminNote] = useState('')
  const [trackingNumber, setTrackingNumber] = useState('')
  const [assessedTotal, setAssessedTotal] = useState('')
  const [payoutTotal, setPayoutTotal] = useState('')
  const [sendPayoutEmail, setSendPayoutEmail] = useState(true)
  const [isCompletingPayout, setIsCompletingPayout] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isSavingItems, setIsSavingItems] = useState(false)
  const [error, setError] = useState('')
  const [isMounted, setIsMounted] = useState(false)
  const [packages, setPackages] = useState<AdminBuybackPackage[]>([])
  const [packageBoxes, setPackageBoxes] = useState('1')
  const [packageKind, setPackageKind] = useState('return')
  const [packageTimeSlot, setPackageTimeSlot] = useState('')
  const [isIssuingPackages, setIsIssuingPackages] = useState(false)
  const [packageError, setPackageError] = useState('')

  const canIssuePackages =
    hasPermission('buyback.package.write') &&
    detail &&
    ['assessed', 'awaiting_customer', 'accepted', 'rejected', 'returned'].includes(detail.status)

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
      setAssessedTotal(res.data.assessed_total != null ? String(res.data.assessed_total) : '')
      setPayoutTotal(res.data.payout_total != null ? String(res.data.payout_total) : '')
      setNextStatus(res.data.allowed_next_statuses[0] || '')
    } catch {
      setError('申込情報の取得に失敗しました')
    } finally {
      setIsLoading(false)
    }
  }, [id])

  const fetchPackages = useCallback(async () => {
    if (!id || Number.isNaN(id) || !hasPermission('buyback.package.read')) {
      setPackages([])
      return
    }
    try {
      const res = await adminBuybackLogisticsApi.listPackages(id)
      setPackages(res.data || [])
    } catch {
      setPackages([])
    }
  }, [id, hasPermission])

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
            assessed_unit_price: draft.assessed_unit_price.trim()
              ? Number(draft.assessed_unit_price)
              : null,
            accepted_unit_price: draft.accepted_unit_price.trim()
              ? Number(draft.accepted_unit_price)
              : null,
            rejection_reason_code: draft.rejection_reason_code || null,
            rejection_reason_text: draft.rejection_reason_text.trim() || null,
            is_return_target: draft.is_return_target,
            is_disposal_target: draft.is_disposal_target,
            return_status: draft.return_status,
            return_tracking_number: draft.return_tracking_number.trim() || null,
            return_shipping_cost: draft.return_shipping_cost.trim()
              ? Number(draft.return_shipping_cost)
              : null,
          }
        }),
        recalculate_assessed_total: true,
        apply_handling_policy: true,
      }
      const res = await adminBuybackApi.updateRequestItems(detail.id, payload)
      setDetail(res.data)
      setItemDrafts(draftsFromDetail(res.data))
      setAssessedTotal(
        res.data.assessed_total != null ? String(res.data.assessed_total) : ''
      )
    } catch {
      setError('商品査定の保存に失敗しました（買取不可理由・減額単価を確認してください）')
    } finally {
      setIsSavingItems(false)
    }
  }

  const handleCompletePayout = async () => {
    if (!detail) return
    const amount = Number(payoutTotal.trim() || detail.payout_total || detail.assessed_total || 0)
    if (!amount || amount <= 0) {
      setError('振込金額を入力してください')
      return
    }
    if (!window.confirm(`振込完了を記録します（${formatYen(amount)}）。よろしいですか？`)) return

    setIsCompletingPayout(true)
    setError('')
    try {
      const res = await adminBuybackApi.completePayout(detail.id, {
        payout_total: amount,
        admin_note: adminNote || undefined,
        send_email: sendPayoutEmail,
        force_email: detail.payout_email_sent && sendPayoutEmail,
      })
      setDetail(res.data)
      setPayoutTotal(res.data.payout_total != null ? String(res.data.payout_total) : '')
      setNextStatus(res.data.allowed_next_statuses[0] || '')
    } catch {
      setError('振込完了の記録に失敗しました（口座未登録などを確認してください）')
    } finally {
      setIsCompletingPayout(false)
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
        payout_total?: number
      } = { status: nextStatus, admin_note: adminNote, tracking_number: trackingNumber }
      if (assessedTotal.trim()) payload.assessed_total = Number(assessedTotal)
      if (payoutTotal.trim()) payload.payout_total = Number(payoutTotal)
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
          <Link href="/admin/buyback/requests" className="text-gray-500 hover:text-gray-900">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <Package className="h-6 w-6 text-yellow-400" />
          <h1 className="text-2xl font-bold text-gray-900">買取申込詳細</h1>
        </div>

        {isLoading ? (
          <p className="text-gray-500">読み込み中...</p>
        ) : !detail ? (
          <p className="text-red-600">{error || 'データが見つかりません'}</p>
        ) : (
          <div className="space-y-6">
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
                {detail.status_label}
              </p>
              <p>
                <span className="text-gray-500">見積 / 査定 / 振込：</span>
                {formatYen(detail.estimated_total)} / {formatYen(detail.assessed_total)} /{' '}
                {formatYen(detail.payout_total)}
              </p>
              {detail.rejected_item_handling_label && (
                <p>
                  <span className="text-gray-500">買取不可時の対応希望：</span>
                  {detail.rejected_item_handling_label}
                </p>
              )}
              {(detail.agreed_prepaid_shipping ||
                detail.agreed_cod_consequence ||
                detail.agreed_condition_rejection) && (
                <p className="text-gray-600">
                  申込同意：元払い {detail.agreed_prepaid_shipping ? '✓' : '—'} / 着払い返送{' '}
                  {detail.agreed_cod_consequence ? '✓' : '—'} / 状態による買取不可{' '}
                  {detail.agreed_condition_rejection ? '✓' : '—'}
                </p>
              )}
              {detail.customer_note && (
                <p>
                  <span className="text-gray-500">お客様メモ：</span>
                  {detail.customer_note}
                </p>
              )}
            </div>

            <div className="border rounded-lg overflow-hidden">
              <div className="bg-gray-50 px-4 py-3 flex items-center justify-between gap-3">
                <h2 className="font-semibold">商品査定</h2>
                <Button onClick={handleSaveItems} disabled={isSavingItems} size="sm">
                  査定内容を保存
                </Button>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-gray-50 border-t">
                    <tr>
                      <th className="px-3 py-2 text-left">商品</th>
                      <th className="px-3 py-2 text-left">査定区分</th>
                      <th className="px-3 py-2 text-left">査定単価</th>
                      <th className="px-3 py-2 text-left">買取不可理由</th>
                      <th className="px-3 py-2 text-left">自由入力</th>
                      <th className="px-3 py-2 text-left">返送/処分</th>
                      <th className="px-3 py-2 text-left">返送状況</th>
                      <th className="px-3 py-2 text-left">追跡番号</th>
                      <th className="px-3 py-2 text-left">返送料</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.items.map((item) => {
                      const draft = itemDrafts[item.id]
                      if (!draft) return null
                      return (
                        <tr key={item.id} className="border-t align-top">
                          <td className="px-3 py-3">
                            <div className="font-medium">{item.product_name_snapshot}</div>
                            <div className="text-gray-500 text-xs mt-1">
                              申込状態 {item.condition_code} / 数量 {item.quantity} / 参考{' '}
                              {formatYen(item.listed_unit_price)}
                            </div>
                          </td>
                          <td className="px-3 py-3">
                            <select
                              className="border rounded-md px-2 py-1 text-sm w-full min-w-[120px]"
                              value={draft.line_status}
                              onChange={(e) =>
                                updateItemDraft(item.id, { line_status: e.target.value })
                              }
                            >
                              {LINE_STATUS_OPTIONS.map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                  {opt.label}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="px-3 py-3">
                            <Input
                              className="min-w-[100px]"
                              placeholder="円"
                              value={draft.assessed_unit_price}
                              onChange={(e) =>
                                updateItemDraft(item.id, { assessed_unit_price: e.target.value })
                              }
                            />
                          </td>
                          <td className="px-3 py-3">
                            <select
                              className="border rounded-md px-2 py-1 text-sm w-full min-w-[160px]"
                              value={draft.rejection_reason_code}
                              onChange={(e) =>
                                updateItemDraft(item.id, {
                                  rejection_reason_code: e.target.value,
                                })
                              }
                            >
                              <option value="">選択</option>
                              {(detail.rejection_reason_options || []).map((opt) => (
                                <option key={opt.code} value={opt.code}>
                                  {opt.label}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="px-3 py-3">
                            <Input
                              className="min-w-[160px]"
                              placeholder="自由入力"
                              value={draft.rejection_reason_text}
                              onChange={(e) =>
                                updateItemDraft(item.id, {
                                  rejection_reason_text: e.target.value,
                                })
                              }
                            />
                          </td>
                          <td className="px-3 py-3">
                            <label className="flex items-center gap-2 mb-2">
                              <input
                                type="checkbox"
                                checked={draft.is_return_target}
                                onChange={(e) =>
                                  updateItemDraft(item.id, {
                                    is_return_target: e.target.checked,
                                  })
                                }
                              />
                              返送
                            </label>
                            <label className="flex items-center gap-2">
                              <input
                                type="checkbox"
                                checked={draft.is_disposal_target}
                                onChange={(e) =>
                                  updateItemDraft(item.id, {
                                    is_disposal_target: e.target.checked,
                                  })
                                }
                              />
                              処分
                            </label>
                          </td>
                          <td className="px-3 py-3">
                            <select
                              className="border rounded-md px-2 py-1 text-sm w-full min-w-[120px]"
                              value={draft.return_status}
                              onChange={(e) =>
                                updateItemDraft(item.id, { return_status: e.target.value })
                              }
                            >
                              {RETURN_STATUS_OPTIONS.map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                  {opt.label}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="px-3 py-3">
                            <Input
                              className="min-w-[120px]"
                              value={draft.return_tracking_number}
                              onChange={(e) =>
                                updateItemDraft(item.id, {
                                  return_tracking_number: e.target.value,
                                })
                              }
                            />
                          </td>
                          <td className="px-3 py-3">
                            <Input
                              className="min-w-[100px]"
                              placeholder="円"
                              value={draft.return_shipping_cost}
                              onChange={(e) =>
                                updateItemDraft(item.id, {
                                  return_shipping_cost: e.target.value,
                                })
                              }
                            />
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {(canIssuePackages || packages.length > 0) && (
              <div className="border rounded-lg p-4 space-y-3">
                <h2 className="font-semibold">梱包バーコード</h2>
                <p className="text-sm text-gray-600">
                  査定完了・返送準備時に発送単位ごとのバーコードを発行します（複数箱対応）。
                </p>
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
                    <label className="text-sm">
                      種別
                      <select
                        className="mt-1 border rounded-md px-3 py-2 text-sm block"
                        value={packageKind}
                        onChange={(e) => setPackageKind(e.target.value)}
                      >
                        <option value="return">返送</option>
                        <option value="outbound">発送</option>
                      </select>
                    </label>
                    <label className="text-sm flex-1 min-w-[160px]">
                      発送希望時間帯
                      <Input
                        className="mt-1"
                        placeholder="例: 14-16時"
                        value={packageTimeSlot}
                        onChange={(e) => setPackageTimeSlot(e.target.value)}
                      />
                    </label>
                    <Button
                      onClick={() => void handleIssuePackages(false)}
                      disabled={isIssuingPackages}
                    >
                      梱包用バーコードを発行
                    </Button>
                    {packages.length > 0 && (
                      <Button
                        variant="outline"
                        onClick={() => void handleIssuePackages(true)}
                        disabled={isIssuingPackages}
                      >
                        再発行
                      </Button>
                    )}
                  </div>
                )}
                {packageError && <p className="text-sm text-red-600">{packageError}</p>}
                {packages.length > 0 && (
                  <div className="space-y-2">
                    <Link
                      href={`/admin/buyback/labels?request_id=${detail.id}`}
                      className="inline-block text-sm text-sky-700 hover:underline"
                    >
                      ラベルCSV / 72265（選択出力）
                    </Link>
                  <div className="overflow-x-auto border rounded-md">
                    <table className="min-w-full text-sm">
                      <thead className="bg-gray-50 text-left">
                        <tr>
                          <th className="px-3 py-2">梱包ID</th>
                          <th className="px-3 py-2">箱</th>
                          <th className="px-3 py-2">種別</th>
                          <th className="px-3 py-2">ステータス</th>
                          <th className="px-3 py-2">希望時間帯</th>
                          <th className="px-3 py-2" />
                        </tr>
                      </thead>
                      <tbody>
                        {packages.map((pkg) => (
                          <tr key={pkg.id} className="border-t">
                            <td className="px-3 py-2 font-mono text-xs">{pkg.package_code}</td>
                            <td className="px-3 py-2">
                              {pkg.box_index}/{pkg.total_boxes}
                            </td>
                            <td className="px-3 py-2">{pkg.package_kind_label || pkg.package_kind}</td>
                            <td className="px-3 py-2">{pkg.status_label || pkg.status}</td>
                            <td className="px-3 py-2">{pkg.preferred_time_slot || '—'}</td>
                            <td className="px-3 py-2 space-x-2 whitespace-nowrap">
                              {hasPermission('buyback.package.write') &&
                                pkg.status === 'packing' && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => void handleCompletePackage(pkg.id)}
                                  >
                                    梱包完了
                                  </Button>
                                )}
                              <Link
                                href={`/admin/buyback/packages/${pkg.id}/print`}
                                className="text-amber-700 hover:underline text-sm"
                              >
                                A4印刷
                              </Link>
                              <Link
                                href={`/admin/buyback/labels?request_id=${detail.id}&package_ids=${pkg.id}`}
                                className="text-sky-700 hover:underline text-sm"
                              >
                                72265
                              </Link>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  </div>
                )}
              </div>
            )}

            {(detail.status === 'payout_pending' || detail.status === 'paid') && (
              <div className="border rounded-lg p-4 space-y-3">
                <h2 className="font-semibold">振込情報</h2>
                {detail.payout_account ? (
                  <div className="text-sm bg-gray-50 rounded-md p-3 space-y-1">
                    <p>
                      <span className="text-gray-500">金融機関：</span>
                      {detail.payout_account.bank_name}
                      {detail.payout_account.branch_name
                        ? ` ${detail.payout_account.branch_name}`
                        : ''}
                    </p>
                    <p>
                      <span className="text-gray-500">口座：</span>
                      {detail.payout_account.account_type_label}{' '}
                      {detail.payout_account.account_number}
                    </p>
                    <p>
                      <span className="text-gray-500">名義：</span>
                      {detail.payout_account.account_holder}
                    </p>
                  </div>
                ) : (
                  <p className="text-sm text-red-600">振込口座が未登録です</p>
                )}
                {!detail.ready_for_payout && detail.status === 'payout_pending' && (
                  <p className="text-sm text-amber-700">
                    KYC・保護者同意・口座のいずれかが未完了の可能性があります
                  </p>
                )}
                {detail.paid_at && (
                  <p className="text-sm">
                    <span className="text-gray-500">振込完了日時：</span>
                    {formatDate(detail.paid_at)}
                    {detail.payout_email_sent && (
                      <span className="text-gray-500 ml-2">（完了メール送信済み）</span>
                    )}
                  </p>
                )}
                {detail.status === 'payout_pending' && (
                  <>
                    <Input
                      placeholder="振込金額（円）"
                      value={payoutTotal}
                      onChange={(e) => setPayoutTotal(e.target.value)}
                    />
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={sendPayoutEmail}
                        onChange={(e) => setSendPayoutEmail(e.target.checked)}
                      />
                      振込完了メールを送信
                    </label>
                    {error && <p className="text-sm text-red-600">{error}</p>}
                    <Button
                      onClick={handleCompletePayout}
                      disabled={isCompletingPayout || !detail.payout_account}
                    >
                      振込完了を記録
                    </Button>
                  </>
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
                  {detail.allowed_next_statuses.map((status) => (
                    <option key={status} value={status}>
                      {STATUS_LABELS[status] || status}
                    </option>
                  ))}
                </select>
                <Input
                  placeholder="追跡番号"
                  value={trackingNumber}
                  onChange={(e) => setTrackingNumber(e.target.value)}
                />
                <Input
                  placeholder="査定金額（円）"
                  value={assessedTotal}
                  onChange={(e) => setAssessedTotal(e.target.value)}
                />
                <Input
                  placeholder="振込金額（円）"
                  value={payoutTotal}
                  onChange={(e) => setPayoutTotal(e.target.value)}
                />
                <Input
                  placeholder="管理者メモ"
                  value={adminNote}
                  onChange={(e) => setAdminNote(e.target.value)}
                />
                {error && <p className="text-sm text-red-600">{error}</p>}
                <Button onClick={handleUpdate} disabled={isSaving || !nextStatus}>
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
