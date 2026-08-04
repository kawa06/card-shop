'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Printer, RefreshCw, ScanLine, Truck } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminApi } from '@/lib/api'
import { Order } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { shippingStatusLabel } from '@/components/admin/AdminOrderShippingForm'

const PENDING_STATUSES = new Set(['unshipped', 'preparing', 'packing'])
const STATUS_LABELS: Record<string, string> = { packing: '条包中', in_transit: '配送中', received: '受取済み' }

function labelForStatus(status: string | null | undefined): string {
  if (!status) return '—'
  return STATUS_LABELS[status] || shippingStatusLabel(status)
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ja-JP')
}

export default function AdminFulfillmentPage() {
  const { isReady } = useAdminGuard()
  const [orders, setOrders] = useState<Order[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => { setIsMounted(true) }, [])

  const fetchOrders = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await adminApi.getAllOrders({ payment_status: 'paid' })
      setOrders((res.data || []).filter((o: Order) => PENDING_STATUSES.has(o.shipping_status || 'unshipped')))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void fetchOrders()
  }, [isMounted, isReady, fetchOrders])

  const counts = useMemo(() => {
    const tally: Record<string, number> = {}
    for (const o of orders) {
      const key = o.shipping_status || 'unshipped'
      tally[key] = (tally[key] || 0) + 1
    }
    return tally
  }, [orders])

  if (!isMounted || !isReady) return null

  return (
    <div className="container py-8 max-w-5xl">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div className="flex items-center gap-3">
          <Link href="/admin"><Button variant="ghost" size="icon" className="text-gray-400 hover:text-gray-900"><ArrowLeft className="h-4 w-4" /></Button></Link>
          <div className="flex items-center gap-2"><Truck className="h-6 w-6 text-orange-500" /><h1 className="text-2xl font-bold text-gray-900">発送管理</h1></div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/admin/orders/scan"><Button variant="outline" size="sm" className="gap-2"><ScanLine className="h-4 w-4" />注文スキャン</Button></Link>
          <Link href="/admin/click-post"><Button variant="outline" size="sm">クリックポストCSV</Button></Link>
          <Button variant="ghost" size="sm" className="gap-2" onClick={() => void fetchOrders()}><RefreshCw className="h-4 w-4" />更新</Button>
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        {['unshipped', 'preparing', 'packing'].map((status) => (
          <div key={status} className="rounded-lg border bg-gray-50 px-4 py-3">
            <p className="text-xs text-gray-500">{labelForStatus(status)}</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{counts[status] || 0}</p>
          </div>
        ))}
        <div className="rounded-lg border bg-orange-50 px-4 py-3">
          <p className="text-xs text-gray-500">合計（発送待ち）</p>
          <p className="text-2xl font-bold text-orange-600 mt-1">{orders.length}</p>
        </div>
      </div>
      {isLoading ? (
        <p className="text-gray-400 animate-pulse">読み込み中...</p>
      ) : orders.length === 0 ? (
        <p className="text-gray-500 rounded-lg border border-dashed p-8 text-center">発送待ちの注文はありません</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-gray-500">
              <tr>
                <th className="px-4 py-3 font-medium">注文</th>
                <th className="px-4 py-3 font-medium">ステータス</th>
                <th className="px-4 py-3 font-medium">購入者</th>
                <th className="px-4 py-3 font-medium">注文日時</th>
                <th className="px-4 py-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id} className="border-t hover:bg-gray-50/80">
                  <td className="px-4 py-3 font-mono">{order.order_number || `#${order.id}`}</td>
                  <td className="px-4 py-3">{labelForStatus(order.shipping_status)}</td>
                  <td className="px-4 py-3">{order.buyer_name || order.buyer_email || '—'}</td>
                  <td className="px-4 py-3">{formatDateTime(order.created_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2">
                      <Link href={`/admin/orders/${order.id}`}><Button variant="outline" size="sm">詳細</Button></Link>
                      <Link href={`/admin/orders/${order.id}/print/shipping-label`}><Button variant="outline" size="sm" className="gap-1"><Printer className="h-3.5 w-3.5" />ラベル</Button></Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
