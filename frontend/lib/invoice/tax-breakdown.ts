import { AdminOrderDetail } from '@/lib/types'
import { itemSubtotal } from '@/lib/admin/order-documents'

export interface TaxBreakdownRow {
  ratePercent: number
  amountInclusive: number
  consumptionTax: number
}

export function taxFromInclusive(amountInclusive: number, ratePercent: number): {
  consumptionTax: number
  amountExcludingTax: number
} {
  const amount = Math.max(0, Math.round(amountInclusive))
  const consumptionTax = Math.round((amount * ratePercent) / (100 + ratePercent))
  return { consumptionTax, amountExcludingTax: amount - consumptionTax }
}

export function buildOrderTaxBreakdown(
  order: AdminOrderDetail,
  defaultTaxRate: number
): TaxBreakdownRow[] {
  const subtotal = itemSubtotal(order)
  const shipping = order.shipping_fee || 0
  const packaging = order.packaging_fee || 0
  const fee = order.payment_fee || 0
  const discount = order.discount_amount || 0

  const grouped = new Map<number, number>()
  const add = (amount: number) => {
    if (amount === 0) return
    grouped.set(defaultTaxRate, (grouped.get(defaultTaxRate) || 0) + amount)
  }

  add(subtotal)
  add(shipping)
  add(packaging)
  add(fee)
  if (discount > 0) add(-discount)

  return Array.from(grouped.entries())
    .sort(([a], [b]) => b - a)
    .map(([ratePercent, amountInclusive]) => {
      const { consumptionTax } = taxFromInclusive(amountInclusive, ratePercent)
      return { ratePercent, amountInclusive, consumptionTax }
    })
    .filter((row) => row.amountInclusive !== 0)
}
