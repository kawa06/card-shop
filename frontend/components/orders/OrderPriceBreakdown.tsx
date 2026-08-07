'use client'

import { Order } from '@/lib/types'
import { t } from '@/lib/i18n'
import {
  orderItemsSubtotal,
  orderShippingBreakdown,
  orderTaxRate,
} from '@/lib/order-pricing'
import { taxFromInclusive } from '@/lib/invoice/tax-breakdown'

interface OrderPriceBreakdownProps {
  order: Order
  lang: 'ja' | 'en'
  formatPrice: (amount: number) => string
  className?: string
  showTax?: boolean
}

export default function OrderPriceBreakdown({
  order,
  lang,
  formatPrice,
  className = '',
  showTax = true,
}: OrderPriceBreakdownProps) {
  const subtotal = orderItemsSubtotal(order)
  const { baseShipping, packagingFee, shippingTotal } = orderShippingBreakdown(order)
  const discount = order.discount_amount || 0
  const pointsUsed = order.points_used || 0
  const pointsEarned = order.points_earned || 0
  const pointsEarnStatus = order.points_earn_status || 'none'
  const paymentFee = order.payment_fee || 0
  const taxRate = orderTaxRate(order)
  const { consumptionTax } = taxFromInclusive(order.total_amount, taxRate)

  const couponLabel =
    order.coupon_name || order.coupon_code
      ? [order.coupon_name, order.coupon_code].filter(Boolean).join(' / ')
      : null

  return (
    <div className={`space-y-1 text-sm ${className}`}>
      <Row label={t('商品小計', lang)} value={formatPrice(subtotal)} />
      <Row label={t('送料', lang)} value={formatPrice(baseShipping)} />
      {packagingFee > 0 && (
        <Row label={t('梱包料', lang)} value={formatPrice(packagingFee)} />
      )}
      {paymentFee > 0 && (
        <Row label={t('手数料', lang)} value={formatPrice(paymentFee)} />
      )}
      {discount > 0 && (
        <Row label={t('割引', lang)} value={`-${formatPrice(discount)}`} valueClass="text-green-600" />
      )}
      {pointsUsed > 0 && (
        <Row
          label={t('ポイント利用', lang)}
          value={`-${pointsUsed.toLocaleString('ja-JP')}pt`}
          valueClass="text-emerald-600"
        />
      )}
      {couponLabel && (
        <Row label={t('クーポン', lang)} value={couponLabel} valueClass="text-gray-600" />
      )}
      {pointsEarnStatus === 'earned' && pointsEarned > 0 && (
        <Row
          label={t('獲得ポイント', lang)}
          value={`+${pointsEarned.toLocaleString('ja-JP')}pt`}
          valueClass="text-yellow-600"
        />
      )}
      {pointsEarnStatus === 'pending' && (
        <Row
          label={t('獲得予定ポイント', lang)}
          value={lang === 'ja' ? '支払後付与' : 'After payment'}
          valueClass="text-gray-500"
          muted
        />
      )}
      {showTax && consumptionTax > 0 && (
        <Row
          label={lang === 'ja' ? `内消費税（${taxRate}%）` : `Tax included (${taxRate}%)`}
          value={formatPrice(consumptionTax)}
          muted
        />
      )}
      <div className="flex justify-between pt-2 mt-2 border-t border-gray-200 font-bold text-base">
        <span className="text-gray-700">{t('合計（税込）', lang)}</span>
        <span className="text-yellow-600">{formatPrice(order.total_amount)}</span>
      </div>
    </div>
  )
}

function Row({
  label,
  value,
  valueClass = 'text-gray-700',
  muted = false,
}: {
  label: string
  value: string
  valueClass?: string
  muted?: boolean
}) {
  return (
    <div className={`flex justify-between ${muted ? 'text-gray-400 text-xs' : ''}`}>
      <span className="text-gray-500">{label}</span>
      <span className={valueClass}>{value}</span>
    </div>
  )
}
