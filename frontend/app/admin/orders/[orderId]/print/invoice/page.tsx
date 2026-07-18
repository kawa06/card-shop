'use client'

import { PrintDocumentFrame } from '@/components/admin/print/PrintDocumentFrame'
import { InvoiceDocument } from '@/components/admin/print/InvoiceDocument'

export default function InvoicePrintPage() {
  return (
    <PrintDocumentFrame
      screenTitle="請求書（印刷プレビュー）"
      getDocumentTitle={(order) => `invoice-${order.order_number || order.id}`}
    >
      {(order) => <InvoiceDocument order={order} />}
    </PrintDocumentFrame>
  )
}
