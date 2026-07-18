'use client'

import { Order } from '@/lib/types'
import { SELLER_INFO } from '@/lib/legal/seller'
import { useShopConfig } from '@/hooks/useShopConfig'
import { useTranslation } from '@/hooks/useTranslation'

const PAYMENT_METHOD_LABELS: Record<string, string> = {
  stripe_card: 'クレジットカード',
  stripe_bank_transfer: '銀行振込（Stripe）',
  bank_transfer: '銀行振込',
  cod: '代金引換',
}

function formatYen(amount: number): string {
  return `¥${Math.round(amount).toLocaleString('ja-JP')}`
}

function formatDateJa(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ja-JP', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function itemSubtotal(order: Order): number {
  return (order.items || []).reduce(
    (sum, item) => sum + (item.unit_price || 0) * (item.quantity || 0),
    0
  )
}

interface OrderReceiptProps {
  order: Order
  buyerName: string
  className?: string
}

function ReceiptItemRow({ item }: { item: Order['items'][number] }) {
  const translatedName = useTranslation(item.card?.name)
  const name =
    item.card?.name_en && translatedName !== item.card.name_en
      ? `${translatedName} (${item.card.name_en})`
      : translatedName || item.card?.name || `カード #${item.card_id}`

  const lineTotal = (item.unit_price || 0) * (item.quantity || 0)

  return (
    <tr className="border-b border-gray-200">
      <td className="py-2 pr-3 text-left align-top text-sm">{name}</td>
      <td className="py-2 px-2 text-right align-top text-sm whitespace-nowrap">
        {formatYen(item.unit_price || 0)}
      </td>
      <td className="py-2 px-2 text-center align-top text-sm">{item.quantity}</td>
      <td className="py-2 pl-2 text-right align-top text-sm whitespace-nowrap font-medium">
        {formatYen(lineTotal)}
      </td>
    </tr>
  )
}

export function OrderReceipt({ order, buyerName, className = '' }: OrderReceiptProps) {
  const { invoiceRegistrationNumber } = useShopConfig()
  const subtotal = itemSubtotal(order)
  const shippingFee = order.shipping_fee || 0
  const total = order.total_amount || subtotal + shippingFee
  const paymentLabel =
    PAYMENT_METHOD_LABELS[order.payment_method || ''] || order.payment_method || '—'
  const issueDate = order.paid_at || order.created_at
  const documentNumber = order.order_number || `#${order.id}`

  return (
    <article
      className={`order-receipt bg-white text-gray-900 ${className}`}
      aria-label="購入明細書"
    >
      <header className="border-b-2 border-gray-900 pb-4 mb-6">
        <div className="flex flex-wrap justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-wide">購入明細書</h1>
            <p className="text-sm text-gray-600 mt-1">Purchase Statement</p>
          </div>
          <div className="text-right text-sm">
            <p>
              <span className="text-gray-500">発行日：</span>
              {formatDateJa(issueDate)}
            </p>
            <p className="font-bold text-base mt-1">注文番号 {documentNumber}</p>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-8 text-sm">
        <section>
          <h2 className="font-bold text-gray-700 mb-2 border-b border-gray-300 pb-1">お買い上げ先</h2>
          <p className="font-medium">{buyerName} 様</p>
          {order.shipping_address && (
            <p className="text-gray-600 mt-1 whitespace-pre-wrap">{order.shipping_address}</p>
          )}
        </section>
        <section>
          <h2 className="font-bold text-gray-700 mb-2 border-b border-gray-300 pb-1">販売事業者</h2>
          <p className="font-medium">{SELLER_INFO.shopName}</p>
          <p>{SELLER_INFO.operatorName}</p>
          {SELLER_INFO.addressLines.map((line) => (
            <p key={line} className="text-gray-600">
              {line}
            </p>
          ))}
          <p className="text-gray-600">{SELLER_INFO.email}</p>
          {invoiceRegistrationNumber && (
            <p className="mt-2 font-medium">登録番号：{invoiceRegistrationNumber}</p>
          )}
        </section>
      </div>

      <section className="mb-6">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b-2 border-gray-900 text-sm">
              <th className="py-2 pr-3 text-left font-bold">商品名</th>
              <th className="py-2 px-2 text-right font-bold whitespace-nowrap">単価（税込）</th>
              <th className="py-2 px-2 text-center font-bold">数量</th>
              <th className="py-2 pl-2 text-right font-bold whitespace-nowrap">小計（税込）</th>
            </tr>
          </thead>
          <tbody>
            {(order.items || []).map((item) => (
              <ReceiptItemRow key={item.id} item={item} />
            ))}
          </tbody>
        </table>
      </section>

      <section className="flex justify-end mb-8">
        <dl className="w-full max-w-xs text-sm space-y-2">
          <div className="flex justify-between">
            <dt className="text-gray-600">商品小計（税込）</dt>
            <dd>{formatYen(subtotal)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-600">送料（税込）</dt>
            <dd>{formatYen(shippingFee)}</dd>
          </div>
          <div className="flex justify-between border-t-2 border-gray-900 pt-2 text-lg font-bold">
            <dt>合計（税込）</dt>
            <dd>{formatYen(total)}</dd>
          </div>
        </dl>
      </section>

      <section className="text-sm border-t border-gray-300 pt-4 space-y-1">
        <p>
          <span className="text-gray-500">支払方法：</span>
          {paymentLabel}
        </p>
        {order.paid_at && (
          <p>
            <span className="text-gray-500">お支払い日時：</span>
            {formatDateJa(order.paid_at)}
          </p>
        )}
        <p className="text-gray-500 text-xs pt-2">
          ※ 本書面は購入内容の明細です。領収書としてご利用いただけます。
          {!invoiceRegistrationNumber &&
            ' 適格請求書発行事業者の登録番号は未設定のため、インボイス制度上の適格請求書には該当しません。'}
        </p>
      </section>
    </article>
  )
}
