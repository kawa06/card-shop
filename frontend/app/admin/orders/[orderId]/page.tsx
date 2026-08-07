'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import {
  ArrowLeft,
  CheckCircle,
  Clock,
  ExternalLink,
  Loader2,
  Printer,
  XCircle,
} from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminApi, adminOrderLogisticsApi } from '@/lib/api'
import { AdminOrderDetail, OrderShipmentLog } from '@/lib/types'
import { usePrice } from '@/lib/format'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { toast } from '@/lib/use-toast'
import {
  AdminOrderShippingForm,
  shippingStatusLabel,
} from '@/components/admin/AdminOrderShippingForm'
import { AdminSendShippingEmailButton } from '@/components/admin/AdminSendShippingEmailButton'
import { resolveOrderDisplayStatus } from '@/lib/order-display-status'
import OrderPriceBreakdown from '@/components/orders/OrderPriceBreakdown'

const paymentStatusLabels: Record<string, string> = {
  awaiting_payment: '入金待ち',
  paid: '支払い済み',
  expired: '期限切れ',
  cancelled: 'キャンセル',
  pending: '未決済',
}

const orderStatusLabels: Record<string, string> = {
  pending: '処理中',
  processing: '準備中',
  shipped: '発送済み',
  delivered: '配達完了',
  cancelled: 'キャンセル',
}

const paymentMethodLabels: Record<string, string> = {
  stripe_card: 'クレジットカード（Stripe）',
  stripe_bank_transfer: '銀行振込（Stripe）',
  bank_transfer: '銀行振込',
  cod: '代金引換',
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ja-JP')
}

function itemSubtotal(order: AdminOrderDetail): number {
  return (order.items || []).reduce(
    (sum, item) => sum + (item.unit_price || 0) * (item.quantity || 0),
    0
  )
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[minmax(7rem,30%)_1fr] gap-2 py-1.5 text-sm border-b border-gray-100 last:border-0">
      <dt className="text-gray-500 shrink-0">{label}</dt>
      <dd className="text-gray-900 break-words">{value ?? '—'}</dd>
    </div>
  )
}

export default function AdminOrderDetailPage() {
  const params = useParams()
  const router = useRouter()
  const { isReady } = useAdminGuard()
  const { formatPrice } = usePrice()
  const [order, setOrder] = useState<AdminOrderDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [extendHours, setExtendHours] = useState('24')
  const [isMounted, setIsMounted] = useState(false)
  const [shipmentLogs, setShipmentLogs] = useState<OrderShipmentLog[]>([])

  const orderId = Number(params.orderId)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const fetchOrder = useCallback(async () => {
    if (!Number.isFinite(orderId) || orderId <= 0) {
      setError('無効な注文IDです')
      setIsLoading(false)
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const [orderRes, logsRes] = await Promise.allSettled([
        adminApi.getOrderById(orderId),
        adminOrderLogisticsApi.getShipmentLogs(orderId),
      ])
      if (orderRes.status === 'fulfilled') {
        setOrder(orderRes.value.data)
      } else {
        throw orderRes.reason
      }
      if (logsRes.status === 'fulfilled') {
        setShipmentLogs(logsRes.value.data || [])
      } else {
        setShipmentLogs([])
      }
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string }; status?: number } })?.response?.data
          ?.detail
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 404) {
        setError('注文が見つかりません')
      } else {
        setError(typeof detail === 'string' ? detail : '注文の取得に失敗しました')
      }
      setOrder(null)
    } finally {
      setIsLoading(false)
    }
  }, [orderId])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void fetchOrder()
  }, [isMounted, isReady, fetchOrder])

  const handleConfirmPayment = async () => {
    if (!order || !confirm('入金を確認し、支払い済みにしますか？')) return
    setActionLoading(true)
    try {
      await adminApi.confirmOrderPayment(order.id)
      toast({ title: '入金を確認しました' })
      fetchOrder()
    } catch {
      toast({ title: 'エラー', description: '入金確認に失敗しました', variant: 'destructive' })
    } finally {
      setActionLoading(false)
    }
  }

  const handleSendPurchaseEmail = async (force = false) => {
    if (!order) return
    if (force && !confirm('購入完了メールを再送しますか？')) return
    if (!force && !confirm('購入完了メールを送信しますか？')) return
    setActionLoading(true)
    try {
      await adminApi.sendPurchaseEmail(order.id, force)
      toast({ title: force ? 'メールを再送しました' : '購入完了メールを送信しました' })
      fetchOrder()
    } catch {
      toast({ title: 'エラー', description: 'メール送信に失敗しました', variant: 'destructive' })
    } finally {
      setActionLoading(false)
    }
  }

  const handleCancelOrder = async () => {
    if (!order || !confirm('注文をキャンセルし、取り置き在庫を解放しますか？')) return
    setActionLoading(true)
    try {
      await adminApi.cancelOrder(order.id)
      toast({ title: '注文をキャンセルしました' })
      fetchOrder()
    } catch {
      toast({ title: 'エラー', description: 'キャンセルに失敗しました', variant: 'destructive' })
    } finally {
      setActionLoading(false)
    }
  }

  const handleExtendDeadline = async () => {
    if (!order) return
    const hours = parseInt(extendHours, 10)
    if (!hours || hours < 1) {
      toast({ title: 'エラー', description: '延長時間を入力してください', variant: 'destructive' })
      return
    }
    setActionLoading(true)
    try {
      await adminApi.extendPaymentDeadline(order.id, hours)
      toast({ title: `支払期限を${hours}時間延長しました` })
      fetchOrder()
    } catch {
      toast({ title: 'エラー', description: '期限延長に失敗しました', variant: 'destructive' })
    } finally {
      setActionLoading(false)
    }
  }

  if (!isMounted || !isReady) return null

  const ps = order?.payment_status || 'pending'
  const isBankTransfer = order?.payment_method === 'stripe_bank_transfer'
  const canManagePayment = ps === 'awaiting_payment' && isBankTransfer
  const subtotal = order ? itemSubtotal(order) : 0

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-4xl">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/admin/orders">
            <Button variant="ghost" size="icon" className="text-gray-400 hover:text-gray-900">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold text-gray-900 truncate">注文詳細</h1>
            {order?.order_number && (
              <p className="text-gray-500 text-sm font-mono">{order.order_number}</p>
            )}
          </div>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center gap-2 py-16 text-gray-400">
            <Loader2 className="h-5 w-5 animate-spin" />
            読み込み中...
          </div>
        )}

        {!isLoading && error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center space-y-4">
            <p className="text-red-700">{error}</p>
            <Button variant="outline" onClick={() => router.push('/admin/orders')}>
              注文一覧へ戻る
            </Button>
          </div>
        )}

        {!isLoading && order && (
          <div className="space-y-6">
            <section className="bg-gray-50 rounded-xl border border-gray-200 p-5">
              <div className="flex flex-wrap items-start gap-3 mb-4">
                <div className="flex-1 min-w-[200px]">
                  <p className="text-lg font-bold text-gray-900">
                    {order.order_number || `注文 #${order.id}`}
                  </p>
                  <p className="text-gray-400 text-xs">内部ID: {order.id}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className="text-xs font-bold px-2 py-1 rounded border bg-white">
                    決済: {paymentStatusLabels[ps] || ps}
                  </span>
                  <span className="text-xs font-bold px-2 py-1 rounded border bg-white">
                    発送: {shippingStatusLabel(resolveOrderDisplayStatus(order))}
                  </span>
                  <span className="text-xs font-bold px-2 py-1 rounded border bg-white">
                    注文: {orderStatusLabels[order.status] || order.status}
                  </span>
                </div>
              </div>
              <p className="text-yellow-500 font-bold text-xl">{formatPrice(order.total_amount)}</p>
            </section>

            <section className="bg-gray-50 rounded-xl border border-gray-200 p-5">
              <h2 className="text-sm font-bold text-gray-700 mb-3">購入者・配送先</h2>
              <dl>
                <InfoRow label="氏名" value={order.buyer_name} />
                <InfoRow label="メール" value={order.buyer_email} />
                <InfoRow label="電話" value={order.buyer_phone} />
                <InfoRow label="郵便番号" value={order.postal_code} />
                <InfoRow
                  label="住所"
                  value={
                    order.shipping_address ||
                    [order.region, order.city, order.address_line1, order.address_line2]
                      .filter(Boolean)
                      .join(' ')
                  }
                />
                <InfoRow label="備考（購入者）" value={order.buyer_note} />
              </dl>
            </section>

            <section className="bg-gray-50 rounded-xl border border-gray-200 p-5">
              <h2 className="text-sm font-bold text-gray-700 mb-3">商品</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 text-left text-gray-500">
                      <th className="py-2 pr-2">商品</th>
                      <th className="py-2 px-2 text-right">単価</th>
                      <th className="py-2 px-2 text-center">数量</th>
                      <th className="py-2 pl-2 text-right">小計</th>
                    </tr>
                  </thead>
                  <tbody>
                    {order.items?.map((item) => {
                      const name = item.card?.name_en
                        ? `${item.card.name} (${item.card.name_en})`
                        : item.card?.name || `カード #${item.card_id}`
                      const lineTotal = (item.unit_price || 0) * (item.quantity || 0)
                      return (
                        <tr key={item.id} className="border-b border-gray-100">
                          <td className="py-3 pr-2">
                            <div className="flex items-center gap-3">
                              {item.card?.image_url && (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img
                                  src={item.card.image_url}
                                  alt=""
                                  className="h-12 w-9 object-cover rounded border border-gray-200 bg-white shrink-0"
                                />
                              )}
                              <div>
                                <p className="text-gray-900">{name}</p>
                                <p className="text-gray-400 text-xs">商品ID: {item.card_id}</p>
                              </div>
                            </div>
                          </td>
                          <td className="py-3 px-2 text-right whitespace-nowrap">
                            {formatPrice(item.unit_price || 0)}
                          </td>
                          <td className="py-3 px-2 text-center">{item.quantity}</td>
                          <td className="py-3 pl-2 text-right whitespace-nowrap font-medium">
                            {formatPrice(lineTotal)}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="bg-gray-50 rounded-xl border border-gray-200 p-5">
              <h2 className="text-sm font-bold text-gray-700 mb-3">金額</h2>
              <OrderPriceBreakdown
                order={order}
                lang="ja"
                formatPrice={formatPrice}
                className="max-w-md ml-auto"
              />
            </section>

            <section className="bg-gray-50 rounded-xl border border-gray-200 p-5">
              <h2 className="text-sm font-bold text-gray-700 mb-3">決済・発送</h2>
              <dl>
                <InfoRow
                  label="支払方法"
                  value={paymentMethodLabels[order.payment_method || ''] || order.payment_method}
                />
                <InfoRow label="購入日時" value={formatDateTime(order.paid_at || order.created_at)} />
                <InfoRow label="配送方法" value={order.shipping_method} />
                <InfoRow label="配送業者" value={order.shipping_carrier} />
                <InfoRow label="追跡番号" value={order.tracking_number} />
                <InfoRow label="発送日" value={formatDateTime(order.shipped_at)} />
                {order.payment_deadline && (
                  <InfoRow label="支払期限" value={formatDateTime(order.payment_deadline)} />
                )}
              </dl>
            </section>

            <section className="bg-gray-50 rounded-xl border border-gray-200 p-5">
              <h2 className="text-sm font-bold text-gray-700 mb-3">内部情報</h2>
              <dl>
                <InfoRow label="Stripe Session" value={order.stripe_checkout_session_id} />
                <InfoRow label="Stripe PaymentIntent" value={order.stripe_payment_intent_id} />
                <InfoRow label="メール状態" value={order.email_send_status} />
                <InfoRow label="購入メール送信" value={formatDateTime(order.purchase_email_sent_at)} />
                <InfoRow label="発送メール送信" value={formatDateTime(order.shipping_email_sent_at)} />
                <InfoRow label="作成日時" value={formatDateTime(order.created_at)} />
                <InfoRow label="最終更新" value={formatDateTime(order.updated_at)} />
                <InfoRow label="管理メモ" value={order.admin_note} />
              </dl>
            </section>

            {canManagePayment && (
              <section className="bg-amber-50 rounded-xl border border-amber-200 p-5 space-y-3">
                <h2 className="text-sm font-bold text-amber-800">入金待ち操作</h2>
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    disabled={actionLoading}
                    onClick={handleConfirmPayment}
                    className="bg-green-600 hover:bg-green-500 text-white"
                  >
                    <CheckCircle className="h-4 w-4 mr-1" />
                    入金確認
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={actionLoading}
                    onClick={handleCancelOrder}
                    className="text-red-600 border-red-300"
                  >
                    <XCircle className="h-4 w-4 mr-1" />
                    キャンセル
                  </Button>
                  <div className="flex items-center gap-2">
                    <Input
                      type="number"
                      min={1}
                      value={extendHours}
                      onChange={(e) => setExtendHours(e.target.value)}
                      className="w-20 h-8 text-sm bg-white"
                    />
                    <span className="text-xs text-gray-600">時間延長</span>
                    <Button size="sm" variant="outline" disabled={actionLoading} onClick={handleExtendDeadline}>
                      期限延長
                    </Button>
                  </div>
                </div>
                {order.payment_deadline && (
                  <p className="text-xs text-amber-700 flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5" />
                    支払期限: {formatDateTime(order.payment_deadline)}
                  </p>
                )}
              </section>
            )}

            <section className="bg-gray-50 rounded-xl border border-gray-200 p-5 space-y-4">
              <h2 className="text-sm font-bold text-gray-700">発送・メール</h2>
              {ps === 'paid' ? (
                <>
                  <AdminOrderShippingForm
                    order={order}
                    disabled={actionLoading}
                    onSaved={fetchOrder}
                  />
                  <AdminSendShippingEmailButton
                    order={order}
                    disabled={actionLoading}
                    onSent={fetchOrder}
                  />
                  <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-gray-200">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={actionLoading}
                      onClick={() => handleSendPurchaseEmail(Boolean(order.purchase_email_sent_at))}
                    >
                      {order.purchase_email_sent_at ? '購入完了メール再送' : '購入完了メール送信'}
                    </Button>
                  </div>
                </>
              ) : (
                <AdminOrderShippingForm order={order} disabled={actionLoading} onSaved={fetchOrder} />
              )}
            </section>

            <section className="bg-gray-50 rounded-xl border border-gray-200 p-5 space-y-3">
              <h2 className="text-sm font-bold text-gray-700">発送ログ</h2>
              {shipmentLogs.length === 0 ? (
                <p className="text-sm text-gray-500">発送ログはまだありません</p>
              ) : (
                <div className="overflow-x-auto rounded-lg border bg-white">
                  <table className="w-full text-xs">
                    <thead className="bg-gray-50 text-left text-gray-500">
                      <tr>
                        <th className="px-3 py-2 font-medium">日時</th>
                        <th className="px-3 py-2 font-medium">イベント</th>
                        <th className="px-3 py-2 font-medium">変更</th>
                        <th className="px-3 py-2 font-medium">追跡番号</th>
                      </tr>
                    </thead>
                    <tbody>
                      {shipmentLogs.map((log) => (
                        <tr key={log.id} className="border-t">
                          <td className="px-3 py-2 whitespace-nowrap">{formatDateTime(log.created_at)}</td>
                          <td className="px-3 py-2">{log.event_type}</td>
                          <td className="px-3 py-2">
                            {log.from_shipping_status || '—'} → {log.to_shipping_status || '—'}
                          </td>
                          <td className="px-3 py-2 font-mono">{log.tracking_number || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="bg-gray-50 rounded-xl border border-gray-200 p-5 space-y-3">
              <h2 className="text-sm font-bold text-gray-700">書類印刷</h2>
              <p className="text-xs text-gray-500">
                A4縦・ブラウザの印刷またはPDF保存に対応しています。印刷時はヘッダー・操作ボタンは非表示になります。
              </p>
              <div className="flex flex-wrap gap-2">
                <Link href={`/admin/orders/${order.id}/print/purchase-statement`}>
                  <Button variant="outline" size="sm" className="gap-2">
                    <Printer className="h-4 w-4" />
                    購入明細書を印刷
                  </Button>
                </Link>
                <Link href={`/admin/orders/${order.id}/print/receipt`}>
                  <Button variant="outline" size="sm" className="gap-2">
                    <Printer className="h-4 w-4" />
                    領収書を印刷
                  </Button>
                </Link>
                <Link href={`/admin/orders/${order.id}/print/invoice`}>
                  <Button variant="outline" size="sm" className="gap-2">
                    <Printer className="h-4 w-4" />
                    請求書を印刷
                  </Button>
                </Link>
                <Link href={`/admin/orders/${order.id}/print/order-copy`}>
                  <Button variant="outline" size="sm" className="gap-2">
                    <Printer className="h-4 w-4" />
                    注文控えを印刷
                  </Button>
                </Link>
                <Link href={`/admin/orders/${order.id}/print/shipping-label`}>
                  <Button variant="outline" size="sm" className="gap-2">
                    <Printer className="h-4 w-4" />
                    発送ラベルを印刷
                  </Button>
                </Link>
                <Link href={`/admin/orders/${order.id}/print/all`}>
                  <Button variant="default" size="sm" className="gap-2">
                    <Printer className="h-4 w-4" />
                    2種類をまとめて印刷
                  </Button>
                </Link>
              </div>
            </section>
          </div>
        )}
      </div>
    </div>
  )
}
