'use client'

import { PrintDocumentFrame } from '@/components/admin/print/PrintDocumentFrame'
import { ReceiptDocument } from '@/components/admin/print/ReceiptDocument'

export default function ReceiptPrintPage() {
  return (
    <PrintDocumentFrame
      screenTitle="領収書（印刷プレビュー）"
      getDocumentTitle={(order) => `receipt-${order.order_number || order.id}`}
    >
      {(order) => <ReceiptDocument order={order} />}
    </PrintDocumentFrame>
  )
}
