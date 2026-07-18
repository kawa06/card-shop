'use client'

import { PrintDocumentFrame } from '@/components/admin/print/PrintDocumentFrame'
import { PurchaseStatementDocument } from '@/components/admin/print/PurchaseStatementDocument'
import { OrderCopyDocument } from '@/components/admin/print/OrderCopyDocument'
import { orderCopyFilename } from '@/lib/admin/order-documents'

export default function PrintAllDocumentsPage() {
  return (
    <PrintDocumentFrame
      screenTitle="購入明細書 + 注文控え（まとめ印刷）"
      getDocumentTitle={(order) => `${orderCopyFilename(order)}-all`}
    >
      {(order) => (
        <div className="print-doc-stack">
          <PurchaseStatementDocument order={order} />
          <div className="print-doc-page-break" aria-hidden />
          <OrderCopyDocument order={order} />
        </div>
      )}
    </PrintDocumentFrame>
  )
}
