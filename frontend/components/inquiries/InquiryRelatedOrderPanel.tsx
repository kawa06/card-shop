'use client'

import { Order } from '@/lib/types'
import {
  formatInquiryOrderStatus,
  formatOrderDate,
  productsForSelectedOrder,
} from '@/lib/inquiry-order-utils'

export function InquiryRelatedOrderPanel({ order }: { order: Order | null }) {
  if (!order) return null

  const items = productsForSelectedOrder(order)

  return (
    <div className="mt-2 rounded-lg border border-blue-100 bg-blue-50/40 p-4 text-sm space-y-2">
      <p className="font-medium text-gray-900">選択中の注文</p>
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-gray-700">
        <div>
          <dt className="text-gray-500 text-xs">注文番号</dt>
          <dd>{order.order_number || `#${order.id}`}</dd>
        </div>
        <div>
          <dt className="text-gray-500 text-xs">注文日</dt>
          <dd>{formatOrderDate(order)}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-gray-500 text-xs">注文状況</dt>
          <dd>{formatInquiryOrderStatus(order)}</dd>
        </div>
      </dl>
      {items.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 mb-1">購入商品</p>
          <ul className="space-y-1">
            {items.map((item) => (
              <li key={item.id} className="text-gray-800">
                {item.card?.name || `商品 #${item.card_id}`}
                <span className="text-gray-500 ml-1">×{item.quantity}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
