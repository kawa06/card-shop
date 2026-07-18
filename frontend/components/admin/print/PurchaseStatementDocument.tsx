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

interface PurchaseStatementDocumentProps {
  order: AdminOrderDetail
}

export function PurchaseStatementDocument({ order }: PurchaseStatementDocumentProps) {
  const subtotal = itemSubtotal(order)
  const shippingFee = order.shipping_fee || 0
  const discount = order.discount_amount || 0
  const paymentFee = order.payment_fee || 0
  const total = order.total_amount ?? subtotal + shippingFee - discount + paymentFee
  const paymentLabel =
    PAYMENT_METHOD_LABELS[order.payment_method || ''] || order.payment_method || '—'
  const purchaseDate = order.paid_at || order.created_at
  const displayOrderNumber = order.order_number || '—'

  return (
    <article className="print-doc-root" aria-label="購入明細書">
      <header className="print-doc-header">
        <div>
          <p className="print-doc-subtitle">{SELLER_INFO.shopName}</p>
          <h1 className="print-doc-title">購入明細書</h1>
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
          <dd className="print-doc-order-number">{displayOrderNumber}</dd>
        </div>
        <div>
          <dt>購入日</dt>
          <dd>{formatDocumentDate(purchaseDate)}</dd>
        </div>
        <div>
          <dt>お買い上げ先</dt>
          <dd>{order.buyer_name || '—'} 様</dd>
        </div>
        <div>
          <dt>支払方法</dt>
          <dd>{paymentLabel}</dd>
        </div>
      </dl>

      <table className="print-doc-table">
        <thead>
          <tr>
            <th>商品名</th>
            <th className="center">数量</th>
            <th className="num">単価（税込）</th>
            <th className="num">小計（税込）</th>
          </tr>
        </thead>
        <tbody>
          {(order.items || []).map((item) => {
            const name = item.card?.name || `商品 #${item.card_id}`
            const lineTotal = (item.unit_price || 0) * (item.quantity || 0)
            return (
              <tr key={item.id}>
                <td>
                  <div className="print-doc-product-cell">
                    {item.card?.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={item.card.image_url}
                        alt=""
                        className="print-doc-product-thumb"
                      />
                    ) : (
                      <div
                        className="print-doc-product-thumb"
                        style={{ background: '#f5f5f5' }}
                        aria-hidden
                      />
                    )}
                    <div>
                      <div className="print-doc-product-name">{name}</div>
                      <div className="print-doc-product-id">商品ID: {item.card_id}</div>
                    </div>
                  </div>
                </td>
                <td className="center">{item.quantity}</td>
                <td className="num">{formatYen(item.unit_price)}</td>
                <td className="num">{formatYen(lineTotal)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <div className="print-doc-totals">
        <div className="print-doc-totals-row">
          <span>商品合計（税込）</span>
          <span>{formatYen(subtotal)}</span>
        </div>
        <div className="print-doc-totals-row">
          <span>送料（税込）</span>
          <span>{formatYen(shippingFee)}</span>
        </div>
        <div className="print-doc-totals-row">
          <span>割引（税込）</span>
          <span>{discount > 0 ? `-${formatYen(discount)}` : formatYen(0)}</span>
        </div>
        <div className="print-doc-totals-row">
          <span>クーポン</span>
          <span>{couponLabel(order)}</span>
        </div>
        <div className="print-doc-totals-row">
          <span>手数料（税込）</span>
          <span>{formatYen(paymentFee)}</span>
        </div>
        <div className="print-doc-totals-row grand">
          <span>お支払い合計（税込）</span>
          <span>{formatYen(total)}</span>
        </div>
      </div>

      {order.buyer_note && (
        <div className="print-doc-footer-note">
          <strong>備考：</strong>
          {order.buyer_note}
        </div>
      )}

      <footer className="print-doc-footer-note">
        <p>
          <strong>お問い合わせ：</strong>
          {SELLER_INFO.email}
        </p>
        <p className="print-doc-disclaimer">※ この書類は領収書ではありません。</p>
      </footer>

      <div className="print-doc-page-footer">{SELLER_INFO.shopName}</div>
    </article>
  )
}
