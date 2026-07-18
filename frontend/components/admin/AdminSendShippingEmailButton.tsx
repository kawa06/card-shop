'use client'

import { useState } from 'react'
import { Mail } from 'lucide-react'
import { Order } from '@/lib/types'
import { adminApi } from '@/lib/api'
import { buildTrackingUrl, isTrackableShippingMethod } from '@/lib/tracking'
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
import { toast } from '@/lib/use-toast'

interface AdminSendShippingEmailButtonProps {
  order: Order
  disabled?: boolean
  onSent: () => void
}

export function AdminSendShippingEmailButton({
  order,
  disabled = false,
  onSent,
}: AdminSendShippingEmailButtonProps) {
  const [open, setOpen] = useState(false)
  const [sending, setSending] = useState(false)

  const tracking = (order.tracking_number || '').trim()
  const needsTracking = isTrackableShippingMethod(order.shipping_method)
  const canSend = order.payment_status === 'paid' && (!needsTracking || tracking.length > 0)
  const trackingUrl = buildTrackingUrl(
    tracking,
    order.shipping_method,
    order.shipping_carrier
  )
  const isResend = Boolean(order.shipping_email_sent_at)

  const handleSend = async () => {
    if (!canSend) {
      toast({
        title: '追跡番号が必要です',
        description: '発送情報を保存してから送信してください',
        variant: 'destructive',
      })
      return
    }
    setSending(true)
    try {
      await adminApi.sendShippingEmail(order.id, isResend)
      toast({ title: isResend ? '発送完了メールを再送しました' : '発送完了メールを送信しました' })
      setOpen(false)
      onSent()
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'メール送信に失敗しました'
      toast({ title: 'エラー', description: String(detail), variant: 'destructive' })
    } finally {
      setSending(false)
    }
  }

  if (order.payment_status !== 'paid') return null

  return (
    <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-gray-200">
      {order.shipping_email_sent_at ? (
        <p className="text-xs text-green-600">
          発送完了メール送信済:{' '}
          {new Date(order.shipping_email_sent_at).toLocaleString('ja-JP')}
        </p>
      ) : (
        <p className="text-xs text-amber-600">
          発送完了メール: 未送信
          {order.email_send_status?.startsWith('shipping_failed')
            ? ` (${order.email_send_status})`
            : ''}
        </p>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
          <Button
            size="sm"
            variant="outline"
            disabled={disabled || !canSend}
            className="text-xs gap-1"
            title={!canSend ? '追跡番号を入力して保存してください' : undefined}
          >
            <Mail className="h-3.5 w-3.5" />
            {isResend ? '発送完了メール再送' : '発送完了メール送信'}
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{isResend ? '発送完了メールを再送' : '発送完了メールを送信'}</DialogTitle>
            <DialogDescription>
              購入者に発送完了のお知らせメールを送信します。内容をご確認ください。
            </DialogDescription>
          </DialogHeader>
          <dl className="text-sm space-y-2 py-2">
            <div className="flex gap-2">
              <dt className="text-gray-500 shrink-0">注文番号</dt>
              <dd className="font-medium">{order.order_number || `#${order.id}`}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-gray-500 shrink-0">購入者</dt>
              <dd>{order.buyer_name || '—'}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-gray-500 shrink-0">配送業者</dt>
              <dd>{order.shipping_carrier || '—'}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-gray-500 shrink-0">追跡番号</dt>
              <dd className="font-mono">{tracking || '—'}</dd>
            </div>
            {trackingUrl && (
              <div className="flex gap-2">
                <dt className="text-gray-500 shrink-0">追跡URL</dt>
                <dd className="text-xs break-all text-purple-600">{trackingUrl}</dd>
              </div>
            )}
          </dl>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} disabled={sending}>
              キャンセル
            </Button>
            <Button onClick={handleSend} disabled={sending || !canSend}>
              {sending ? '送信中...' : '送信する'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
