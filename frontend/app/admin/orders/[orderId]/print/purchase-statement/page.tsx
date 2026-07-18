'use client'

import { PrintDocumentFrame } from '@/components/admin/print/PrintDocumentFrame'
import { PurchaseStatementDocument } from '@/components/admin/print/PurchaseStatementDocument'
import { purchaseStatementFilename } from '@/lib/admin/order-documents'

export default function PurchaseStatementPrintPage() {
  return (
    <PrintDocumentFrame
      screenTitle="購入明細書（印刷プレビュー）"
      getDocumentTitle={purchaseStatementFilename}
    >
      {(order) => <PurchaseStatementDocument order={order} />}
    </PrintDocumentFrame>
  )
}
