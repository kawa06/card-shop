import { AdminOrderDetail } from '@/lib/types'
import { SELLER_INFO } from '@/lib/legal/seller'
import { shippingStatusLabel } from '@/components/admin/AdminOrderShippingForm'
import {
  ORDER_STATUS_LABELS,
  PAYMENT_METHOD_LABELS,
  PAYMENT_STATUS_LABELS,
  couponLabel,
  formatDocumentDateTime,
  formatShippingAddress,
  formatYen,
  itemSubtotal,
  stripePaymentIds,
} from '@/lib/admin/order-documents'

interface OrderCopyDocumentProps {
  order: AdminOrderDetail
}

function InfoRow({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="print-doc-info-row">
      <span className="print-doc-info-label">{label}</span>
      <span className={`print-doc-info-value${mono ? ' mono' : ''}`}>{value ?? '—'}</span>
    </div>
  )
}

export function OrderCopyDocument({ order }: OrderCopyDocumentProps) {
  const subtotal = itemSubtotal(order)
  const shippingFee = order.shipping_fee || 0
  const packagingFee = order.packaging_fee || 0
  const discount = order.discount_amount || 0
  const paymentFee = order.payment_fee || 0
  const total = order.total_amount ?? subtotal + shippingFee + packagingFee - discount + paymentFee
  const paymentLabel =
    PAYMENT_METHOD_LABELS[order.payment_method || ''] || order.payment_method || '—'
  const ps = order.payment_status || 'pending'
  const purchaseDateTime = order.paid_at || order.created_at

  return (
    <article className="print-doc-root" aria-label="注文控え">
      <header className="print-doc-header">
        <div>
          <p className="print-doc-subtitle">{SELLER_INFO.shopName}</p>
          <h1 className="print-doc-title">注文控え</h1>
          <p className="print-doc-subtitle">店舗保管用（内部情報含む）</p>
        </div>
      </header>

      <section className="print-doc-meta">
        <div>
          <dt>注文番号</dt>
          <dd className="print-doc-order-number">{order.order_number || '—'}</dd>
        </div>
        <div>
          <dt>注文ID（内部）</dt>
          <dd className="print-doc-order-number">{order.id}</dd>
        </div>
        <div style={{ gridColumn: '1 / -1' }}>
          <dt>決済ID（Stripe等）</dt>
          <dd className="mono" style={{ fontFamily: 'ui-monospace, monospace', fontSize: '8.5pt' }}>
            {stripePaymentIds(order)}
          </dd>
        </div>
        <div>
          <dt>購入日時</dt>
          <dd>{formatDocumentDateTime(purchaseDateTime)}</dd>
        </div>
        <div>
          <dt>作成日時</dt>
          <dd>{formatDocumentDateTime(order.created_at)}</dd>
        </div>
      </section>

      <h2 className="print-doc-section-title">購入者・配送先</h2>
      <div className="print-doc-info-grid">
        <InfoRow label="氏名" value={order.buyer_name} />
        <InfoRow label="メール" value={order.buyer_email} />
        <InfoRow label="電話" value={order.buyer_phone} />
        <InfoRow label="郵便番号" value={order.postal_code ? `〒${order.postal_code}` : '—'} />
        <InfoRow label="配送先" value={formatShippingAddress(order)} />
        <InfoRow label="備考（購入者）" value={order.buyer_note} />
      </div>

      <h2 className="print-doc-section-title">商品明細</h2>
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
          <span>梱包料（税込）</span>
          <span>{formatYen(packagingFee)}</span>
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
          <span>支払合計（税込）</span>
          <span>{formatYen(total)}</span>
        </div>
      </div>

      <h2 className="print-doc-section-title" style={{ marginTop: '16px' }}>
        決済・発送・管理
      </h2>
      <div className="print-doc-info-grid">
        <InfoRow label="支払方法" value={paymentLabel} />
        <InfoRow label="決済状況" value={PAYMENT_STATUS_LABELS[ps] || ps} />
        <InfoRow label="注文状況" value={ORDER_STATUS_LABELS[order.status] || order.status} />
        <InfoRow
          label="発送状況"
          value={shippingStatusLabel(order.shipping_status)}
        />
        <InfoRow label="配送方法" value={order.shipping_method} />
        <InfoRow label="配送業者" value={order.shipping_carrier} />
        <InfoRow label="追跡番号" value={order.tracking_number} mono />
        <InfoRow label="発送日" value={formatDocumentDateTime(order.shipped_at)} />
        <InfoRow label="最終更新" value={formatDocumentDateTime(order.updated_at)} />
        <InfoRow label="メール状態" value={order.email_send_status} />
      </div>

      {order.admin_note && (
        <div className="print-doc-footer-note">
          <strong>管理者用メモ：</strong>
          {order.admin_note}
        </div>
      )}

      <div className="print-doc-page-footer">{SELLER_INFO.shopName} — 注文控え</div>
    </article>
  )
}
