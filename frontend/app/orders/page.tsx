'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Package, ChevronDown, ChevronUp } from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { ordersApi } from '@/lib/api'
import { Order } from '@/lib/types'

const statusLabels: Record<string, { label: string; color: string }> = {
  pending: { label: '処理中', color: 'text-yellow-400' },
  processing: { label: '準備中', color: 'text-blue-400' },
  shipped: { label: '発送済み', color: 'text-purple-400' },
  delivered: { label: '配達完了', color: 'text-green-400' },
  cancelled: { label: 'キャンセル', color: 'text-red-400' },
}

export default function OrdersPage() {
  const router = useRouter()
  const { isAuthenticated } = useAuthStore()
  const [orders, setOrders] = useState<Order[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login')
      return
    }
    ordersApi.getAll().then((res) => {
      setOrders(res.data || [])
    }).catch(() => {}).finally(() => setIsLoading(false))
  }, [isAuthenticated, router])

  if (!isAuthenticated) return null

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-gray-400 animate-pulse">読み込み中...</div>
      </div>
    )
  }

  if (orders.length === 0) {
    return (
      <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center gap-4">
        <Package className="h-16 w-16 text-gray-700" />
        <h2 className="text-xl font-bold text-white">注文履歴はありません</h2>
        <p className="text-gray-400 text-sm">まだ注文がありません</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="container py-8 max-w-3xl">
        <h1 className="text-2xl font-bold text-white mb-6">注文履歴</h1>

        <div className="space-y-3">
          {orders.map((order) => {
            const status = statusLabels[order.status] || { label: order.status, color: 'text-gray-400' }
            const isExpanded = expandedId === order.id

            return (
              <div key={order.id} className="bg-gray-900 rounded-lg border border-white/10">
                <button
                  onClick={() => setExpandedId(isExpanded ? null : order.id)}
                  className="w-full flex items-center justify-between p-4 text-left"
                >
                  <div className="flex items-center gap-4">
                    <div>
                      <p className="text-white font-medium">注文 #{order.id}</p>
                      <p className="text-gray-500 text-sm">
                        {new Date(order.created_at).toLocaleDateString('ja-JP')}
                      </p>
                    </div>
                    <span className={`text-sm font-medium ${status.color}`}>{status.label}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-yellow-400 font-bold">¥{order.total_amount.toLocaleString()}</span>
                    {isExpanded ? (
                      <ChevronUp className="h-4 w-4 text-gray-400" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-gray-400" />
                    )}
                  </div>
                </button>

                {isExpanded && (
                  <div className="border-t border-white/10 p-4 space-y-3">
                    {order.items?.map((item) => (
                      <div key={item.id} className="flex justify-between items-center text-sm">
                        <span className="text-gray-300">{item.card?.name || `カード #${item.card_id}`}</span>
                        <span className="text-gray-400">
                          ¥{(item.unit_price || 0).toLocaleString()} × {item.quantity}
                        </span>
                      </div>
                    ))}
                    {order.shipping_address && (
                      <div className="border-t border-white/10 pt-3 text-sm">
                        <span className="text-gray-500">配送先: </span>
                        <span className="text-gray-300">{order.shipping_address}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
