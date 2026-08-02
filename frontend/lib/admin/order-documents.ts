import { AdminOrderDetail } from '@/lib/types'

export const PAYMENT_METHOD_LABELS: Record<string, string> = {
  stripe_card: 'クレジットカード',
  stripe_bank_transfer: '銀行振込（Stripe）',
  bank_transfer: '銀行振込',
  cod: '代金引換',
}

export const PAYMENT_STATUS_LABELS: Record<string, string> = {
  awaiting_payment: '入金待ち',
  paid: '支払い済み',
  expired: '期限切れ',
  cancelled: 'キャンセル',
  pending: '未決済',
}

export const ORDER_STATUS_LABELS: Record<string, string> = {
  pending: '処理中',
  processing: '準備中',
  shipped: '発送済み',
  delivered: '配達完了',
  cancelled: 'キャンセル',
}

export function formatYen(amount: number | null | undefined): string {
  const n = Math.round(Number(amount) || 0)
  return `¥${n.toLocaleString('ja-JP')}`
}

export function formatDocumentDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ja-JP', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

export function formatDocumentDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ja-JP')
}

export function itemSubtotal(order: AdminOrderDetail): number {
  if (order.items_subtotal != null && order.items_subtotal > 0) {
    return order.items_subtotal
  }
  return (order.items || []).reduce(
    (sum, item) => sum + (item.unit_price || 0) * (item.quantity || 0),
    0
  )
}

export function couponLabel(order: AdminOrderDetail): string {
  if (order.coupon_name && order.coupon_code) {
    return `${order.coupon_name}（${order.coupon_code}）`
  }
  return order.coupon_name || order.coupon_code || '—'
}

export function purchaseStatementFilename(order: AdminOrderDetail): string {
  const num = order.order_number || String(order.id)
  return `purchase-statement-${num}`
}

export function orderCopyFilename(order: AdminOrderDetail): string {
  const num = order.order_number || String(order.id)
  return `order-copy-${num}`
}

export function formatShippingAddress(order: AdminOrderDetail): string {
  if (order.shipping_address) return order.shipping_address
  const parts = [
    order.postal_code ? `〒${order.postal_code}` : null,
    order.region,
    order.city,
    order.address_line1,
    order.address_line2,
  ].filter(Boolean)
  return parts.join(' ') || '—'
}

export function stripePaymentIds(order: AdminOrderDetail): string {
  const parts: string[] = []
  if (order.stripe_checkout_session_id) {
    parts.push(`Session: ${order.stripe_checkout_session_id}`)
  }
  if (order.stripe_payment_intent_id) {
    parts.push(`PaymentIntent: ${order.stripe_payment_intent_id}`)
  }
  return parts.length > 0 ? parts.join(' / ') : '—'
}
