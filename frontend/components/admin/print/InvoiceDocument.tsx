import Image from 'next/image'
import { AdminOrderDetail } from '@/lib/types'
import { SELLER_INFO } from '@/lib/legal/seller'
import {
  PAYMENT_METHOD_LABELS,
  couponLabel,
  formatDocumentDate,
  formatShippingAddress,
  formatYen,
  itemSubtotal,
} from '@/lib/admin/order-documents'
import { useInvoiceConfig } from '@/hooks/useInvoiceConfig'
import { QualifiedInvoiceSection } from '@/components/admin/print/QualifiedInvoiceSection'
import { OrderLineItemsTable } from '@/components/admin/print/OrderLineItemsTable'

interface InvoiceDocumentProps {
  order: AdminOrderDetail
}

export function InvoiceDocument({ order }: InvoiceDocumentProps) {
  const invoiceConfig = useInvoiceConfig()
  const subtotal = itemSubtotal(order)
  const shippingFee = order.shipping_fee || 0
  const packagingFee = order.packaging_fee || 0
  const discount = order.discount_amount || 0
  const paymentFee = order.payment_fee || 0
  const total = order.total_amount ?? subtotal + shippingFee + packagingFee - discount + paymentFee
  const paymentLabel =
    PAYMENT_METHOD_LABELS[order.payment_method || ''] || order.payment_method || '—'
  const issueDate = order.paid_at || order.created_at

  return (
    <article className="print-doc-root" aria-label="請求書">
      <header className="print-doc-header">
        <div>
          <p className="print-doc-subtitle">{SELLER_INFO.shopName}</p>
          <h1 className="print-doc-title">請求書</h1>
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
          <dt>請求書番号</dt>
          <dd className="print-doc-order-number">{order.order_number || '—'}</dd>
        </div>
        <div>
          <dt>請求日</dt>
          <dd>{formatDocumentDate(issueDate)}</dd>
        </div>
        <div>
          <dt>請求先</dt>
          <dd>{order.buyer_name || '—'} 様</dd>
        </div>
        <div>
          <dt>支払方法</dt>
          <dd>{paymentLabel}</dd>
        </div>
        <div style={{ gridColumn: '1 / -1' }}>
          <dt>請求先住所</dt>
          <dd>{formatShippingAddress(order)}</dd>
        </div>
      </dl>

      <QualifiedInvoiceSection order={order} config={invoiceConfig} />

      <OrderLineItemsTable order={order} />

      <div className="print-doc-totals">
        <div className="print-doc-totals-row">
          <span>商品合計（税込）</span>
          <span>{formatYen(subtotal)}</span>
        </div>
        <div className="print-doc-totals-row">
          <span>送料（税込）</span>
          <span>{formatYen(shippingFee)}</span>
        </div>
        {packagingFee > 0 && (
          <div className="print-doc-totals-row">
            <span>梱包料（税込）</span>
            <span>{formatYen(packagingFee)}</span>
          </div>
        )}
        {discount > 0 && (
          <div className="print-doc-totals-row">
            <span>割引（税込）</span>
            <span>-{formatYen(discount)}</span>
          </div>
        )}
        {(order.coupon_name || order.coupon_code) && (
          <div className="print-doc-totals-row">
            <span>クーポン</span>
            <span>{couponLabel(order)}</span>
          </div>
        )}
        {paymentFee > 0 && (
          <div className="print-doc-totals-row">
            <span>手数料（税込）</span>
            <span>{formatYen(paymentFee)}</span>
          </div>
        )}
        <div className="print-doc-totals-row grand">
          <span>ご請求金額（税込）</span>
          <span>{formatYen(total)}</span>
        </div>
      </div>

      <footer className="print-doc-footer-note">
        <p>
          <strong>お問い合わせ：</strong>
          {SELLER_INFO.email}
        </p>
      </footer>

      <div className="print-doc-page-footer">{SELLER_INFO.shopName}</div>
    </article>
  )
}
