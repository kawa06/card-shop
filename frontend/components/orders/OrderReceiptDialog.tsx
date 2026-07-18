'use client'

import type { ReactNode } from 'react'
import { Printer } from 'lucide-react'
import { Order } from '@/lib/types'
import { OrderReceipt } from '@/components/orders/OrderReceipt'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

interface OrderReceiptDialogProps {
  order: Order
  buyerName: string
  trigger?: ReactNode
}

export function OrderReceiptDialog({ order, buyerName, trigger }: OrderReceiptDialogProps) {
  const handlePrint = () => {
    document.body.classList.add('printing-order-receipt')
    window.print()
    window.setTimeout(() => {
      document.body.classList.remove('printing-order-receipt')
    }, 500)
  }

  const canShow = order.payment_status === 'paid'

  if (!canShow) return null

  return (
    <Dialog>
      <DialogTrigger asChild>
        {trigger || (
          <Button type="button" variant="outline" size="sm" className="gap-2">
            <Printer className="h-4 w-4" />
            領収書・明細
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader className="no-print">
          <DialogTitle>購入明細書</DialogTitle>
          <DialogDescription>
            内容を確認のうえ、印刷または PDF 保存（ブラウザの「PDF に保存」）してください。
          </DialogDescription>
        </DialogHeader>

        <div id="order-receipt-print-root" className="order-receipt-print-root px-1">
          <OrderReceipt order={order} buyerName={buyerName} />
        </div>

        <DialogFooter className="no-print">
          <Button type="button" onClick={handlePrint} className="gap-2">
            <Printer className="h-4 w-4" />
            印刷 / PDF保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
