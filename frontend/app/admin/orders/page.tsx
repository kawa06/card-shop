'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { ArrowLeft, ChevronDown, ChevronUp, Clock, CheckCircle, XCircle, Search } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminApi } from '@/lib/api'
import { Order } from '@/lib/types'
import { usePrice } from '@/lib/format'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { toast } from '@/lib/use-toast'
import {
  AdminOrderShippingForm,
  shippingStatusColors,
  shippingStatusLabel,
} from '@/components/admin/AdminOrderShippingForm'
import { AdminSendShippingEmailButton } from '@/components/admin/AdminSendShippingEmailButton'

const paymentStatusLabels: Record<string, string> = {
  awaiting_payment: '入金待ち',
  paid: '支払い済み',
  expired: '期限切れ',
  cancelled: 'キャンセル',
  pending: '未決済',
}

const paymentStatusColors: Record<string, string> = {
  awaiting_payment: 'text-amber-500 bg-amber-500/10 border-amber-500/30',
  paid: 'text-green-600 bg-green-500/10 border-green-500/30',
  expired: 'text-gray-500 bg-gray-500/10 border-gray-500/30',
  cancelled: 'text-red-500 bg-red-500/10 border-red-500/30',
}

function formatDeadline(deadline: string | null): string {
  if (!deadline) return '—'
  return new Date(deadline).toLocaleString('ja-JP')
}

function isDeadlinePast(deadline: string | null): boolean {
  if (!deadline) return false
  return new Date(deadline).getTime() < Date.now()
}

export default function AdminOrdersPage() {
  const { isReady } = useAdminGuard()
  const { formatPrice } = usePrice()
  const [orders, setOrders] = useState<Order[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [isMounted, setIsMounted] = useState(false)
  const [paymentFilter, setPaymentFilter] = useState<string>('')
  const [shippingFilter, setShippingFilter] = useState<string>('')
  const [searchInput, setSearchInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [extendHours, setExtendHours] = useState<Record<number, string>>({})
  const [actionLoading, setActionLoading] = useState<number | null>(null)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => setSearchQuery(searchInput.trim()), 400)
    return () => window.clearTimeout(timer)
  }, [searchInput])

  const fetchAll = useCallback(async () => {
    setIsLoading(true)
    try {
      const params: {
        payment_status?: string
        shipping_status?: string
        q?: string
      } = {}
      if (paymentFilter) params.payment_status = paymentFilter
      if (shippingFilter) params.shipping_status = shippingFilter
      if (searchQuery) params.q = searchQuery
      const res = await adminApi.getAllOrders(params)
      setOrders(res.data || [])
    } finally {
      setIsLoading(false)
    }
  }, [paymentFilter, shippingFilter, searchQuery])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void fetchAll()
  }, [isMounted, isReady, fetchAll])

  const handleConfirmPayment = async (orderId: number) => {
    if (!confirm('入金を確認し、支払い済みにしますか？\n（注文番号発行・購入完了メール送信を含みます）')) return
    setActionLoading(orderId)
    try {
      await adminApi.confirmOrderPayment(orderId)
      toast({ title: '入金を確認しました' })
      fetchAll()
    } catch {
      toast({ title: 'エラー', description: '入金確認に失敗しました', variant: 'destructive' })
    } finally {
      setActionLoading(null)
    }
  }

  const handleSendPurchaseEmail = async (orderId: number, force = false) => {
    if (force && !confirm('購入完了メールを再送しますか？')) return
    if (!force && !confirm('購入完了メールを送信しますか？')) return
    setActionLoading(orderId)
    try {
      await adminApi.sendPurchaseEmail(orderId, force)
      toast({ title: force ? 'メールを再送しました' : '購入完了メールを送信しました' })
      fetchAll()
    } catch {
      toast({ title: 'エラー', description: 'メール送信に失敗しました', variant: 'destructive' })
    } finally {
      setActionLoading(null)
    }
  }

  const handleCancelOrder = async (orderId: number) => {
    if (!confirm('注文をキャンセルし、取り置き在庫を解放しますか？')) return
    setActionLoading(orderId)
    try {
      await adminApi.cancelOrder(orderId)
      toast({ title: '注文をキャンセルしました' })
      fetchAll()
    } catch {
      toast({ title: 'エラー', description: 'キャンセルに失敗しました', variant: 'destructive' })
    } finally {
      setActionLoading(null)
    }
  }

  const handleExtendDeadline = async (orderId: number) => {
    const hours = parseInt(extendHours[orderId] || '24', 10)
    if (!hours || hours < 1) {
      toast({ title: 'エラー', description: '延長時間を入力してください', variant: 'destructive' })
      return
    }
    setActionLoading(orderId)
    try {
      await adminApi.extendPaymentDeadline(orderId, hours)
      toast({ title: `支払期限を${hours}時間延長しました` })
      setExtendHours((prev) => ({ ...prev, [orderId]: '' }))
      fetchAll()
    } catch {
      toast({ title: 'エラー', description: '期限延長に失敗しました', variant: 'destructive' })
    } finally {
      setActionLoading(null)
    }
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-5xl">
        <div className="flex items-center gap-3 mb-4">
          <Link href="/admin">
            <Button variant="ghost" size="icon" className="text-gray-400 hover:text-gray-900">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 flex-1">注文管理</h1>
        </div>

        <div className="flex flex-col sm:flex-row flex-wrap gap-3 mb-6">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="注文番号・氏名・メール・追跡番号・ID"
              className="pl-9 bg-white"
            />
          </div>
          <select
            value={paymentFilter}
            onChange={(e) => setPaymentFilter(e.target.value)}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900"
          >
            <option value="">すべての決済状態</option>
            <option value="awaiting_payment">入金待ち</option>
            <option value="paid">支払い済み</option>
            <option value="expired">期限切れ</option>
            <option value="cancelled">キャンセル</option>
          </select>
          <select
            value={shippingFilter}
            onChange={(e) => setShippingFilter(e.target.value)}
            className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900"
          >
            <option value="">すべての発送状態</option>
            <option value="unshipped">未発送</option>
            <option value="preparing">準備中</option>
            <option value="shipped">発送済み</option>
            <option value="delivered">配達完了</option>
            <option value="cancelled">キャンセル</option>
          </select>
        </div>

        <div className="bg-gray-50 rounded-xl border border-gray-200 overflow-hidden">
          {isLoading ? (
            <div className="p-8 text-center text-gray-400 animate-pulse">読み込み中...</div>
          ) : orders.length === 0 ? (
            <div className="p-8 text-center text-gray-500">注文はありません</div>
          ) : (
            <div className="divide-y divide-gray-200">
              {orders.map((order) => {
                const isExpanded = expandedId === order.id
                const ps = order.payment_status || 'pending'
                const ss = order.shipping_status || 'unshipped'
                const isBankTransfer = order.payment_method === 'stripe_bank_transfer'
                const canManagePayment = ps === 'awaiting_payment' && isBankTransfer

                return (
                  <div key={order.id}>
                    <div className="flex flex-wrap items-center gap-3 p-4">
                      <button
                        onClick={() => setExpandedId(isExpanded ? null : order.id)}
                        className="text-gray-400"
                        aria-label={isExpanded ? '閉じる' : '詳細を開く'}
                      >
                        {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      </button>
                      <div className="flex-1 min-w-[160px]">
                        <p className="text-gray-900 font-medium">
                          {order.order_number || `注文 #${order.id}`}
                        </p>
                        {order.order_number && (
                          <p className="text-gray-400 text-xs">ID #{order.id}</p>
                        )}
                        {(order.buyer_name || order.buyer_email) && (
                          <p className="text-gray-600 text-xs mt-0.5">
                            {order.buyer_name}
                            {order.buyer_email && (
                              <span className="text-gray-400"> · {order.buyer_email}</span>
                            )}
                          </p>
                        )}
                        <p className="text-gray-500 text-xs">
                          {order.created_at ? new Date(order.created_at).toLocaleString('ja-JP') : '不明'}
                        </p>
                        {order.tracking_number && (
                          <p className="text-purple-600 text-xs font-mono mt-0.5">
                            追跡: {order.tracking_number}
                          </p>
                        )}
                      </div>
                      <span
                        className={`text-xs font-bold px-2 py-1 rounded border ${paymentStatusColors[ps] || 'text-gray-500'}`}
                      >
                        {paymentStatusLabels[ps] || ps}
                      </span>
                      <span
                        className={`text-xs font-bold px-2 py-1 rounded border ${shippingStatusColors[ss] || 'text-gray-500'}`}
                      >
                        {shippingStatusLabel(ss)}
                      </span>
                      {order.stock_reserved && ps === 'awaiting_payment' && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-orange-500/10 text-orange-600 border border-orange-500/20">
                          取り置き中
                        </span>
                      )}
                      <span className="text-yellow-400 font-bold">{formatPrice(order.total_amount || 0)}</span>
                    </div>

                    {isExpanded && (
                      <div className="bg-black/5 px-6 pb-5 space-y-3">
                        {order.items?.map((item) => {
                          const displayName = item.card?.name_en
                            ? `${item.card.name} (${item.card.name_en})`
                            : item.card?.name || `カード #${item.card_id}`
                          return (
                            <div key={item.id} className="flex justify-between text-sm">
                              <span className="text-gray-600">{displayName}</span>
                              <span className="text-gray-400">
                                {formatPrice(item.unit_price || 0)} × {item.quantity}
                              </span>
                            </div>
                          )
                        })}

                        {order.shipping_address && (
                          <p className="text-xs text-gray-500">配送先: {order.shipping_address}</p>
                        )}

                        {isBankTransfer && order.payment_deadline && (
                          <div
                            className={`flex items-center gap-2 text-xs ${isDeadlinePast(order.payment_deadline) && ps === 'awaiting_payment' ? 'text-red-500' : 'text-gray-500'}`}
                          >
                            <Clock className="h-3.5 w-3.5" />
                            支払期限: {formatDeadline(order.payment_deadline)}
                          </div>
                        )}

                        {canManagePayment && (
                          <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-200">
                            <Button
                              size="sm"
                              disabled={actionLoading === order.id}
                              onClick={() => handleConfirmPayment(order.id)}
                              className="bg-green-600 hover:bg-green-500 text-white text-xs"
                            >
                              <CheckCircle className="h-3.5 w-3.5 mr-1" />
                              入金確認
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={actionLoading === order.id}
                              onClick={() => handleCancelOrder(order.id)}
                              className="text-red-600 border-red-300 text-xs"
                            >
                              <XCircle className="h-3.5 w-3.5 mr-1" />
                              キャンセル
                            </Button>
                            <div className="flex items-center gap-2">
                              <Input
                                type="number"
                                min={1}
                                placeholder="24"
                                value={extendHours[order.id] || ''}
                                onChange={(e) =>
                                  setExtendHours((prev) => ({ ...prev, [order.id]: e.target.value }))
                                }
                                className="w-20 h-8 text-xs bg-white"
                              />
                              <span className="text-xs text-gray-500">時間延長</span>
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={actionLoading === order.id}
                                onClick={() => handleExtendDeadline(order.id)}
                                className="text-xs"
                              >
                                期限延長
                              </Button>
                            </div>
                          </div>
                        )}

                        {ps === 'paid' && (
                          <>
                            <AdminOrderShippingForm
                              order={order}
                              disabled={actionLoading === order.id}
                              onSaved={fetchAll}
                            />
                            <AdminSendShippingEmailButton
                              order={order}
                              disabled={actionLoading === order.id}
                              onSent={fetchAll}
                            />
                            <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-gray-200">
                              {order.purchase_email_sent_at ? (
                                <p className="text-xs text-green-600">
                                  購入完了メール送信済: {formatDeadline(order.purchase_email_sent_at)}
                                </p>
                              ) : (
                                <p className="text-xs text-amber-600">
                                  購入完了メール: 未送信
                                  {order.email_send_status ? ` (${order.email_send_status})` : ''}
                                </p>
                              )}
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={actionLoading === order.id}
                                onClick={() =>
                                  handleSendPurchaseEmail(order.id, Boolean(order.purchase_email_sent_at))
                                }
                                className="text-xs"
                              >
                                {order.purchase_email_sent_at ? '購入完了メール再送' : '購入完了メール送信'}
                              </Button>
                            </div>
                          </>
                        )}

                        {ps !== 'paid' && (
                          <AdminOrderShippingForm
                            order={order}
                            disabled={actionLoading === order.id}
                            onSaved={fetchAll}
                          />
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
