'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { ArrowLeft, Loader2, Printer } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminApi } from '@/lib/api'
import { AdminOrderDetail } from '@/lib/types'
import { Button } from '@/components/ui/button'

interface PrintDocumentFrameProps {
  children: (order: AdminOrderDetail) => React.ReactNode
  getDocumentTitle: (order: AdminOrderDetail) => string
  screenTitle: string
}

export function PrintDocumentFrame({
  children,
  getDocumentTitle,
  screenTitle,
}: PrintDocumentFrameProps) {
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
    } catch {
      setError('注文の取得に失敗しました')
      setOrder(null)
    } finally {
      setIsLoading(false)
    }
  }, [orderId])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void fetchOrder()
  }, [isMounted, isReady, fetchOrder])

  useEffect(() => {
    if (!order) return
    document.title = getDocumentTitle(order)
  }, [order, getDocumentTitle])

  const handlePrint = () => {
    window.print()
  }

  if (!isMounted || !isReady) return null

  return (
    <div className="print-doc-wrapper min-h-screen bg-gray-100 py-6 px-4">
      <div className="no-print max-w-[210mm] mx-auto mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Link href={`/admin/orders/${orderId}`}>
            <Button variant="ghost" size="sm" className="gap-1">
              <ArrowLeft className="h-4 w-4" />
              注文詳細へ
            </Button>
          </Link>
          <h1 className="text-sm font-medium text-gray-700">{screenTitle}</h1>
        </div>
        <Button onClick={handlePrint} disabled={!order} className="gap-2">
          <Printer className="h-4 w-4" />
          印刷 / PDF保存
        </Button>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center gap-2 py-20 text-gray-400 no-print">
          <Loader2 className="h-5 w-5 animate-spin" />
          読み込み中...
        </div>
      )}

      {!isLoading && error && (
        <div className="no-print max-w-md mx-auto rounded-lg border border-red-200 bg-red-50 p-6 text-center text-red-700">
          {error}
        </div>
      )}

      {!isLoading && order && children(order)}
    </div>
  )
}
