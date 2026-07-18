import { Card, Order, OrderItem } from '@/lib/types'

export const PAYMENT_STATUS_LABELS: Record<string, string> = {
  awaiting_payment: '入金待ち',
  paid: '支払い済み',
  expired: '期限切れ',
  cancelled: 'キャンセル',
  pending: '未決済',
}

export const SHIPPING_STATUS_LABELS: Record<string, string> = {
  unshipped: '未発送',
  preparing: '発送準備中',
  shipped: '発送済み',
  delivered: '配達完了',
}

export const ORDER_STATUS_LABELS: Record<string, string> = {
  pending: '保留',
  processing: '処理中',
  completed: '完了',
  cancelled: 'キャンセル',
}

export function formatInquiryOrderStatus(order: Order): string {
  const payment = order.payment_status
    ? PAYMENT_STATUS_LABELS[order.payment_status] || order.payment_status
    : '—'
  const shipping = order.shipping_status
    ? SHIPPING_STATUS_LABELS[order.shipping_status] || order.shipping_status
    : null
  if (shipping) return `${payment} / ${shipping}`
  return payment
}

export function formatOrderDate(order: Order): string {
  const d = order.paid_at || order.created_at
  return d ? new Date(d).toLocaleDateString('ja-JP') : '—'
}

export interface OrderProductOption {
  cardId: number
  name: string
  orderId: number
  orderLabel: string
}

export function collectProductsFromOrders(orders: Order[]): OrderProductOption[] {
  const seen = new Set<number>()
  const out: OrderProductOption[] = []
  for (const order of orders) {
    for (const item of order.items || []) {
      if (!item.card_id || seen.has(item.card_id)) continue
      seen.add(item.card_id)
      out.push({
        cardId: item.card_id,
        name: item.card?.name || `商品 #${item.card_id}`,
        orderId: order.id,
        orderLabel: order.order_number || `#${order.id}`,
      })
    }
  }
  return out
}

export function productsForSelectedOrder(order: Order | null): OrderItem[] {
  if (!order?.items?.length) return []
  return order.items
}

export function findOrderById(orders: Order[], id: string | number): Order | null {
  const n = typeof id === 'string' ? parseInt(id, 10) : id
  if (!n) return null
  return orders.find((o) => o.id === n) || null
}

export function findProductLabel(orders: Order[], productId: string, orderId?: string): string {
  const pid = parseInt(productId, 10)
  if (!pid) return ''
  if (orderId) {
    const order = findOrderById(orders, orderId)
    const item = productsForSelectedOrder(order).find((i) => i.card_id === pid)
    return item?.card?.name || ''
  }
  return collectProductsFromOrders(orders).find((p) => p.cardId === pid)?.name || ''
}
