import Image from 'next/image'
import { AdminOrderDetail } from '@/lib/types'
import { SELLER_INFO } from '@/lib/legal/seller'
import {
  PAYMENT_METHOD_LABELS,
  couponLabel,
  formatDocumentDate,
  formatYen,
  itemSubtotal,
} from '@/lib/admin/order-documents'
import { useInvoiceConfig } from '@/hooks/useInvoiceConfig'
import { QualifiedInvoiceSection } from '@/components/admin/print/QualifiedInvoiceSection'
import { OrderLineItemsTable } from '@/components/admin/print/OrderLineItemsTable'

interface ReceiptDocumentProps {
  order: AdminOrderDetail
}

export function ReceiptDocument({ order }: ReceiptDocumentProps) {
  const invoiceConfig = useInvoiceConfig()
  const subtotal = itemSubtotal(order)
  const shippingFee = order.shipping_fee || 0
  const discount = order.discount_amount || 0
  const paymentFee = order.payment_fee || 0
  const total = order.total_amount ?? subtotal + shippingFee - discount + paymentFee
  const paymentLabel =
    PAYMENT_METHOD_LABELS[order.payment_method || ''] || order.payment_method || '—'
  const issueDate = order.paid_at || order.created_at

  return (
    <article className="print-doc-root" aria-label="領収書">
      <header className="print-doc-header">
        <div>
          <p className="print-doc-subtitle">{SELLER_INFO.shopName}</p>
          <h1 className="print-doc-title">領収書</h1>
        </div>
        <Image
          src="/logo-main.png"
          alt={SELLER_INFO.shopName}
          width={120}
          height={44}
          className="print-doc-logo"
          priority
        />
      </header>

      <dl className="print-doc-meta">
        <div>
          <dt>注文番号</dt>
          <dd className="print-doc-order-number">{order.order_number || '—'}</dd>
        </div>
        <div>
          <dt>発行日</dt>
          <dd>{formatDocumentDate(issueDate)}</dd>
        </div>
        <div>
          <dt>宛名</dt>
          <dd>{order.buyer_name || '—'} 様</dd>
        </div>
        <div>
          <dt>支払方法</dt>
          <dd>{paymentLabel}</dd>
        </div>
      </dl>

      <QualifiedInvoiceSection order={order} config={invoiceConfig} />

      <OrderLineItemsTable order={order} />

      <div className="print-doc-totals">
        <div className="print-doc-totals-row grand">
          <span>領収金額（税込）</span>
          <span>{formatYen(total)}</span>
        </div>
        <div className="print-doc-totals-row">
          <span>内訳：商品合計</span>
          <span>{formatYen(subtotal)}</span>
        </div>
        <div className="print-doc-totals-row">
          <span>送料</span>
          <span>{formatYen(shippingFee)}</span>
        </div>
        {discount > 0 && (
          <div className="print-doc-totals-row">
            <span>割引</span>
            <span>-{formatYen(discount)}</span>
          </div>
        )}
        {paymentFee > 0 && (
          <div className="print-doc-totals-row">
            <span>手数料</span>
            <span>{formatYen(paymentFee)}</span>
          </div>
        )}
        {(order.coupon_name || order.coupon_code) && (
          <div className="print-doc-totals-row">
            <span>クーポン</span>
            <span>{couponLabel(order)}</span>
          </div>
        )}
      </div>

      <footer className="print-doc-footer-note">
        <p>
          <strong>但し：</strong>
          商品代金として上記正に領収いたしました。
        </p>
        <p>
          <strong>お問い合わせ：</strong>
          {SELLER_INFO.email}
        </p>
      </footer>

      <div className="print-doc-page-footer">{SELLER_INFO.shopName}</div>
    </article>
  )
}
