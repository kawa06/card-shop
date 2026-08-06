'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { ArrowLeft, Loader2, Printer } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminApi } from '@/lib/api'
import { AdminOrderDetail } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { shippingStatusLabel } from '@/components/admin/AdminOrderShippingForm'
import { AdminAuthenticatedSvgImage } from '@/components/admin/AdminAuthenticatedSvgImage'

const STATUS_LABELS: Record<string, string> = {
  packing: '梱包中',
  in_transit: '配送中',
  received: '受取済み',
}

function labelForStatus(status: string | null | undefined): string {
  if (!status) return '—'
  return STATUS_LABELS[status] || shippingStatusLabel(status)
}

export default function AdminShippingLabelPrintPage() {
  const params = useParams()
  const { isReady } = useAdminGuard()
  const [order, setOrder] = useState<AdminOrderDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isMounted, setIsMounted] = useState(false)
  const orderId = Number(params.orderId)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const fetchOrder = useCallback(async () => {
    if (!Number.isFinite(orderId) || orderId <= 0) {
      setError('無効な注文IDです')
      setIsLoading(false)
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const res = await adminApi.getOrderById(orderId)
      setOrder(res.data)
      try {
        await adminApi.getOrderBarcode(orderId)
      } catch {
        // Barcode is ensured lazily by the authenticated SVG fetch.
      }
    } catch {
      setError('注文情報を取得できませんでした')
      setOrder(null)
    } finally {
      setIsLoading(false)
    }
  }, [orderId])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void fetchOrder()
  }, [isMounted, isReady, fetchOrder])

  if (!isMounted || !isReady) return null

  return (
    <div className="print-doc-wrapper min-h-screen bg-gray-100 py-6 px-4">
      <div className="no-print max-w-md mx-auto mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Link href={`/admin/orders/${orderId}`}>
            <Button variant="ghost" size="sm" className="gap-1">
              <ArrowLeft className="h-4 w-4" /> 注文詳細へ
            </Button>
          </Link>
          <h1 className="text-sm font-medium text-gray-700">発送ラベル（印刷プレビュー）</h1>
        </div>
        <Button onClick={() => window.print()} disabled={!order} className="gap-2">
          <Printer className="h-4 w-4" /> 印刷 / PDF保存
        </Button>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center gap-2 py-20 text-gray-400 no-print">
          <Loader2 className="h-5 w-5 animate-spin" /> 読み込み中...
        </div>
      )}
      {!isLoading && error && (
        <div className="no-print max-w-md mx-auto rounded-lg border border-red-200 bg-red-50 p-6 text-center text-red-700">
          {error}
        </div>
      )}
      {!isLoading && order && (
        <div className="mx-auto w-[100mm] bg-white border shadow-sm p-4 print:shadow-none print:border-0">
          <p className="text-[10px] text-gray-500 uppercase tracking-wide">Shipping Label</p>
          <p className="text-lg font-bold font-mono mt-1">{order.order_number || `#${order.id}`}</p>
          <p className="text-xs text-gray-600 mt-2">{labelForStatus(order.shipping_status)}</p>
          <div className="mt-4 border-t pt-3 space-y-1 text-xs">
            <p className="font-medium">{order.buyer_name || '—'}</p>
            <p>{order.postal_code ? `〒${order.postal_code}` : ''}</p>
            <p>
              {order.region}
              {order.city}
              {order.address_line1}
            </p>
            {order.address_line2 && <p>{order.address_line2}</p>}
            {order.buyer_phone && <p>TEL: {order.buyer_phone}</p>}
          </div>
          <div className="mt-4 flex justify-center">
            <AdminAuthenticatedSvgImage
              apiPath={`/admin/orders/${order.id}/barcode.svg`}
              alt="Order barcode"
              className="max-w-full h-16 object-contain"
            />
          </div>
          {order.tracking_number && (
            <p className="text-center text-[10px] font-mono mt-2">追跡: {order.tracking_number}</p>
          )}
        </div>
      )}
    </div>
  )
}
