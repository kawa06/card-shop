'use client'

import { PrintDocumentFrame } from '@/components/admin/print/PrintDocumentFrame'
import { OrderCopyDocument } from '@/components/admin/print/OrderCopyDocument'
import { orderCopyFilename } from '@/lib/admin/order-documents'

export default function OrderCopyPrintPage() {
  return (
    <PrintDocumentFrame
      screenTitle="注文控え（印刷プレビュー）"
      getDocumentTitle={orderCopyFilename}
    >
      {(order) => <OrderCopyDocument order={order} />}
    </PrintDocumentFrame>
  )
}
