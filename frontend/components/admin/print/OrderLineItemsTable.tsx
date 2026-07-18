import { AdminOrderDetail } from '@/lib/types'
import { formatYen } from '@/lib/admin/order-documents'

interface OrderLineItemsTableProps {
  order: AdminOrderDetail
}

export function OrderLineItemsTable({ order }: OrderLineItemsTableProps) {
  return (
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
                    <img src={item.card.image_url} alt="" className="print-doc-product-thumb" />
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
  )
}
