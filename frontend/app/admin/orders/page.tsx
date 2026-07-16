'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft, ChevronDown, ChevronUp } from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { adminApi } from '@/lib/api'
import { Order } from '@/lib/types'
import { usePrice } from '@/lib/format'
import { Button } from '@/components/ui/button'
import { toast } from '@/lib/use-toast'

const statusOptions = [
  { value: 'pending', label: '処理中' },
  { value: 'processing', label: '準備中' },
  { value: 'shipped', label: '発送済み' },
  { value: 'delivered', label: '配達完了' },
  { value: 'cancelled', label: 'キャンセル' },
]

const statusColors: Record<string, string> = {
  pending: 'text-yellow-400',
  processing: 'text-blue-400',
  shipped: 'text-purple-400',
  delivered: 'text-green-400',
  cancelled: 'text-red-400',
}

export default function AdminOrdersPage() {
  const router = useRouter()
  const { isAuthenticated, user, isLoading: isAuthLoading } = useAuthStore()
  const { formatPrice } = usePrice()
  const [orders, setOrders] = useState<Order[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  useEffect(() => {
    if (!isMounted || isAuthLoading) return

    if (!isAuthenticated) {
      router.push('/login')
      return
    }
    if (user && !user.is_admin) {
      router.push('/')
      return
    }
    fetchAll()
  }, [isMounted, isAuthenticated, user, isAuthLoading, router])

  const fetchAll = async () => {
    setIsLoading(true)
    try {
      const res = await adminApi.getAllOrders()
      setOrders(res.data || [])
    } finally {
      setIsLoading(false)
    }
  }

  const handleStatusChange = async (orderId: number, newStatus: string) => {
    try {
      await adminApi.updateOrderStatus(orderId, newStatus)
      toast({ title: 'ステータスを更新しました' })
      fetchAll()
    } catch {
      toast({ title: 'エラー', description: '更新に失敗しました', variant: 'destructive' })
    }
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-5xl">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/admin">
            <Button variant="ghost" size="icon" className="text-gray-400 hover:text-gray-900">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">注文管理</h1>
        </div>

        <div className="bg-gray-50 rounded-xl border border-gray-200 overflow-hidden">
          {isLoading ? (
            <div className="p-8 text-center text-gray-400 animate-pulse">読み込み中...</div>
          ) : orders.length === 0 ? (
            <div className="p-8 text-center text-gray-500">注文はありません</div>
          ) : (
            <div className="divide-y divide-gray-200">
              {orders.map((order) => {
                const isExpanded = expandedId === order.id
                return (
                  <div key={order.id}>
                    <div className="flex items-center gap-4 p-4">
                      <button onClick={() => setExpandedId(isExpanded ? null : order.id)} className="text-gray-400">
                        {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      </button>
                      <div className="flex-1">
                        <p className="text-gray-900 font-medium">注文 #{order.id}</p>
                        <p className="text-gray-500 text-xs">
                          {order.created_at ? new Date(order.created_at).toLocaleString('ja-JP') : '不明'}
                        </p>
                      </div>
                      <span className={`text-sm font-medium ${statusColors[order.status] || 'text-gray-400'}`}>
                        {statusOptions.find(s => s.value === order.status)?.label || order.status}
                      </span>
                      <span className="text-yellow-400 font-bold">{formatPrice(order.total_amount || 0)}</span>
                      <select
                        value={order.status}
                        onChange={(e) => handleStatusChange(order.id, e.target.value)}
                        className="rounded-md border border-gray-300 bg-white px-2 py-1 text-sm text-gray-900"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {statusOptions.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                      </select>
                    </div>
                    {isExpanded && order.items && (
                      <div className="bg-black/20 px-12 pb-4 space-y-2">
                        {order.items.map((item) => {
                          const displayName = item.card?.name_en ? `${item.card.name} (${item.card.name_en})` : (item.card?.name || `カード #${item.card_id}`)
                          return (
                            <div key={item.id} className="flex justify-between text-sm">
                              <span className="text-gray-600">{displayName}</span>
                              <span className="text-gray-400">{formatPrice(item.unit_price || 0)} × {item.quantity}</span>
                            </div>
                          )
                        })}
                        {order.shipping_address && (
                          <p className="text-xs text-gray-500 pt-1">配送先: {order.shipping_address}</p>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
