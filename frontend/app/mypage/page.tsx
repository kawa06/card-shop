'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { User, Package, Heart, MapPin } from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { ordersApi } from '@/lib/api'
import { Order } from '@/lib/types'

export default function MypagePage() {
  const router = useRouter()
  const { isAuthenticated, user } = useAuthStore()
  const [orders, setOrders] = useState<Order[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login')
      return
    }
    ordersApi.getAll().then((res) => {
      setOrders((res.data || []).slice(0, 3))
    }).catch(() => {}).finally(() => setIsLoading(false))
  }, [isAuthenticated, router])

  if (!isAuthenticated || !user) return null

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="container py-8 max-w-3xl">
        <h1 className="text-2xl font-bold text-white mb-6">マイページ</h1>

        {/* Profile Card */}
        <div className="bg-gray-900 rounded-xl border border-white/10 p-6 mb-6">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-yellow-400/10 border border-yellow-400/20 flex items-center justify-center">
              <User className="h-8 w-8 text-yellow-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">{user.name}</h2>
              <p className="text-gray-400 text-sm">{user.email}</p>
              {user.is_admin && (
                <span className="text-xs bg-yellow-400/20 text-yellow-400 px-2 py-0.5 rounded border border-yellow-400/20 mt-1 inline-block">
                  管理者
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <Link href="/orders">
            <div className="bg-gray-900 rounded-lg border border-white/10 p-4 flex items-center gap-3 hover:border-yellow-400/30 transition-colors cursor-pointer">
              <Package className="h-6 w-6 text-yellow-400" />
              <div>
                <p className="text-white font-medium text-sm">注文履歴</p>
                <p className="text-gray-500 text-xs">{isLoading ? '...' : `${orders.length}件以上`}</p>
              </div>
            </div>
          </Link>
          <div className="bg-gray-900 rounded-lg border border-white/10 p-4 flex items-center gap-3 opacity-50">
            <Heart className="h-6 w-6 text-pink-400" />
            <div>
              <p className="text-white font-medium text-sm">お気に入り</p>
              <p className="text-gray-500 text-xs">準備中</p>
            </div>
          </div>
          <div className="bg-gray-900 rounded-lg border border-white/10 p-4 flex items-center gap-3 opacity-50">
            <MapPin className="h-6 w-6 text-blue-400" />
            <div>
              <p className="text-white font-medium text-sm">住所管理</p>
              <p className="text-gray-500 text-xs">準備中</p>
            </div>
          </div>
        </div>

        {/* Recent Orders */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-white font-semibold">最近の注文</h2>
            <Link href="/orders" className="text-yellow-400 text-sm hover:text-yellow-300">
              すべて見る →
            </Link>
          </div>
          {isLoading ? (
            <div className="space-y-2">
              {[1, 2].map((i) => (
                <div key={i} className="h-16 bg-gray-900 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : orders.length === 0 ? (
            <p className="text-gray-500 text-sm">注文履歴はありません</p>
          ) : (
            <div className="space-y-2">
              {orders.map((order) => (
                <div key={order.id} className="flex justify-between items-center bg-gray-900 rounded-lg border border-white/10 p-4">
                  <div>
                    <p className="text-white text-sm font-medium">注文 #{order.id}</p>
                    <p className="text-gray-500 text-xs">
                      {new Date(order.created_at).toLocaleDateString('ja-JP')}
                    </p>
                  </div>
                  <span className="text-yellow-400 font-bold">¥{order.total.toLocaleString()}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
