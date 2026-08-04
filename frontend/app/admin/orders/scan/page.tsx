'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, ExternalLink } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminOrderLogisticsApi } from '@/lib/api'
import type { OrderScanResult } from '@/lib/types'
import { BuybackBarcodeScanner } from '@/components/admin/buyback/BuybackBarcodeScanner'
import { Button } from '@/components/ui/button'
import { shippingStatusLabel } from '@/components/admin/AdminOrderShippingForm'

const STATUS_LABELS: Record<string, string> = { packing: '条包中', in_transit: '配送中', received: '受取済み' }

function labelForStatus(status: string | null | undefined): string {
  if (!status) return '—'
  return STATUS_LABELS[status] || shippingStatusLabel(status)
}

function deviceInfo(): string {
  return [navigator.userAgent || '', `viewport:${window.innerWidth}x${window.innerHeight}`].join(' | ').slice(0, 240)
}

export default function AdminOrderScanPage() {
  const { isReady } = useAdminGuard()
  const [isMounted, setIsMounted] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<OrderScanResult | null>(null)

  useEffect(() => { setIsMounted(true) }, [])

  const handleScan = useCallback(async (code: string) => {
    setScanning(true)
    setError(null)
    try {
      const res = await adminOrderLogisticsApi.scanOrder(code, deviceInfo())
      setResult(res.data)
    } catch {
      setError('注文が見つかりません。バーコードを確認してください。')
      setResult(null)
    } finally {
      setScanning(false)
    }
  }, [])

  if (!isMounted || !isReady) return null

  return (
    <div className="container py-8 max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/admin/fulfillment"><Button variant="ghost" size="icon" className="text-gray-400 hover:text-gray-900"><ArrowLeft className="h-4 w-4" /></Button></Link>
        <h1 className="text-2xl font-bold text-gray-900">注文スキャン</h1>
      </div>
      <p className="text-sm text-gray-500 mb-4">注文バーコードをスキャンすると、注文番号・発送ステータスを表示します。</p>
      <BuybackBarcodeScanner onScan={handleScan} disabled={scanning} />
      {error && <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
      {result && (
        <div className="mt-6 rounded-xl border bg-gray-50 p-5 space-y-3">
          <h2 className="text-sm font-bold text-gray-700">スキャン結果</h2>
          <dl className="grid grid-cols-[minmax(6rem,30%)_1fr] gap-2 text-sm">
            <dt className="text-gray-500">注文番号</dt><dd className="font-mono">{result.order_number || `#${result.order_id}`}</dd>
            <dt className="text-gray-500">発送ステータス</dt><dd>{labelForStatus(result.shipping_status)}</dd>
            <dt className="text-gray-500">購入者</dt><dd>{result.buyer_name || '—'}</dd>
            <dt className="text-gray-500">追跡番号</dt><dd className="font-mono">{result.tracking_number || '—'}</dd>
          </dl>
          <div className="flex flex-wrap gap-2 pt-2">
            <Link href={`/admin/orders/${result.order_id}`}><Button size="sm" className="gap-2"><ExternalLink className="h-4 w-4" />注文詳細を開く</Button></Link>
            <Link href={`/admin/orders/${result.order_id}/print/shipping-label`}><Button size="sm" variant="outline">発送ラベルを印刷</Button></Link>
          </div>
        </div>
      )}
    </div>
  )
}
