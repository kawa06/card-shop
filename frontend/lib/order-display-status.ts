import { Order } from '@/lib/types'

/** Prefer cancelled/expired state over stale shipping_status like "unshipped". */
export function resolveOrderDisplayStatus(order: Pick<Order, 'shipping_status' | 'status' | 'payment_status'>): string {
  if (order.payment_status === 'cancelled' || order.payment_status === 'expired') {
    return 'cancelled'
  }
  if (order.status === 'cancelled') {
    return 'cancelled'
  }
  return order.shipping_status || order.status || 'pending'
}
