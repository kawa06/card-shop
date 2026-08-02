import { Order } from '@/lib/types'

/** Subtotal from stored snapshot or line items (purchase-time prices). */
export function orderItemsSubtotal(order: Order): number {
  if (order.items_subtotal != null && order.items_subtotal > 0) {
    return order.items_subtotal
  }
  return (order.items || []).reduce(
    (sum, item) => sum + (item.unit_price || 0) * (item.quantity || 0),
    0
  )
}

/**
 * Shipping breakdown for display.
 * Legacy orders store packaging inside shipping_fee when packaging_fee is 0.
 */
export function orderShippingBreakdown(order: Order): {
  baseShipping: number
  packagingFee: number
  shippingTotal: number
} {
  const packaging = order.packaging_fee || 0
  const shipping = order.shipping_fee || 0
  if (packaging > 0) {
    return {
      baseShipping: shipping,
      packagingFee: packaging,
      shippingTotal: shipping + packaging,
    }
  }
  return {
    baseShipping: shipping,
    packagingFee: 0,
    shippingTotal: shipping,
  }
}

export function orderLineItemName(
  item: Order['items'][number],
  lang: 'ja' | 'en' = 'ja'
): string {
  if (item.product_name) return item.product_name
  if (lang === 'en' && item.card?.name_en) return item.card.name_en
  return item.card?.name || `商品 #${item.card_id}`
}

export function orderTaxRate(order: Order, fallback = 10): number {
  return order.tax_rate_snapshot ?? fallback
}
