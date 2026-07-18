'use client'

import { useEffect, useState } from 'react'
import { Save } from 'lucide-react'
import { Order } from '@/lib/types'
import { adminApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { toast } from '@/lib/use-toast'

const SHIPPING_STATUS_OPTIONS = [
  { value: 'unshipped', label: '未発送' },
  { value: 'preparing', label: '準備中' },
  { value: 'shipped', label: '発送済み' },
  { value: 'delivered', label: '配達完了' },
  { value: 'cancelled', label: 'キャンセル' },
]

export { SHIPPING_STATUS_OPTIONS }

function toDatetimeLocalValue(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function formatShippedAt(value: string): string | null {
  if (!value.trim()) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return null
  return d.toISOString()
}

interface ShippingDraft {
  shipping_status: string
  shipping_carrier: string
  tracking_number: string
  shipped_at: string
  admin_note: string
}

function draftFromOrder(order: Order): ShippingDraft {
  return {
    shipping_status: order.shipping_status || 'unshipped',
    shipping_carrier: order.shipping_carrier || '',
    tracking_number: order.tracking_number || '',
    shipped_at: toDatetimeLocalValue(order.shipped_at),
    admin_note: order.admin_note || '',
  }
}

interface AdminOrderShippingFormProps {
  order: Order
  disabled?: boolean
  onSaved: () => void
}

export function AdminOrderShippingForm({
  order,
  disabled = false,
  onSaved,
}: AdminOrderShippingFormProps) {
  const [draft, setDraft] = useState<ShippingDraft>(() => draftFromOrder(order))
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setDraft(draftFromOrder(order))
  }, [order])

  const handleSave = async () => {
    setSaving(true)
    try {
      await adminApi.updateOrderShipping(order.id, {
        shipping_status: draft.shipping_status,
        shipping_carrier: draft.shipping_carrier.trim() || null,
        tracking_number: draft.tracking_number.trim() || null,
        shipped_at: formatShippedAt(draft.shipped_at),
        admin_note: draft.admin_note.trim() || null,
      })
      toast({ title: '発送情報を保存しました' })
      onSaved()
    } catch {
      toast({ title: 'エラー', description: '発送情報の保存に失敗しました', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="border-t border-gray-200 pt-3 space-y-3">
      <p className="text-xs font-bold text-gray-700">発送管理</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label className="text-xs space-y-1 block">
          <span className="text-gray-500">発送ステータス</span>
          <select
            value={draft.shipping_status}
            onChange={(e) => setDraft((prev) => ({ ...prev, shipping_status: e.target.value }))}
            className="w-full rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm text-gray-900"
            disabled={disabled || saving}
          >
            {SHIPPING_STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs space-y-1 block">
          <span className="text-gray-500">配送業者</span>
          <Input
            value={draft.shipping_carrier}
            onChange={(e) => setDraft((prev) => ({ ...prev, shipping_carrier: e.target.value }))}
            placeholder="例: 日本郵便、ヤマト"
            className="h-8 text-sm bg-white"
            disabled={disabled || saving}
          />
        </label>
        <label className="text-xs space-y-1 block">
          <span className="text-gray-500">追跡番号</span>
          <Input
            value={draft.tracking_number}
            onChange={(e) => setDraft((prev) => ({ ...prev, tracking_number: e.target.value }))}
            placeholder="追跡番号（発送完了メール送信に必要）"
            className="h-8 text-sm bg-white font-mono"
            disabled={disabled || saving}
          />
        </label>
        <label className="text-xs space-y-1 block">
          <span className="text-gray-500">発送日時</span>
          <Input
            type="datetime-local"
            value={draft.shipped_at}
            onChange={(e) => setDraft((prev) => ({ ...prev, shipped_at: e.target.value }))}
            className="h-8 text-sm bg-white"
            disabled={disabled || saving}
          />
        </label>
      </div>
      <label className="text-xs space-y-1 block">
        <span className="text-gray-500">管理メモ（お客様には表示されません）</span>
        <textarea
          value={draft.admin_note}
          onChange={(e) => setDraft((prev) => ({ ...prev, admin_note: e.target.value }))}
          rows={2}
          className="w-full rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm text-gray-900"
          disabled={disabled || saving}
        />
      </label>
      <Button
        size="sm"
        onClick={handleSave}
        disabled={disabled || saving}
        className="text-xs gap-1"
      >
        <Save className="h-3.5 w-3.5" />
        {saving ? '保存中...' : '発送情報を保存'}
      </Button>
    </div>
  )
}

export function shippingStatusLabel(status: string | null | undefined): string {
  return SHIPPING_STATUS_OPTIONS.find((o) => o.value === status)?.label || status || '—'
}

export const shippingStatusColors: Record<string, string> = {
  unshipped: 'text-gray-500 bg-gray-500/10 border-gray-500/30',
  preparing: 'text-blue-500 bg-blue-500/10 border-blue-500/30',
  shipped: 'text-purple-500 bg-purple-500/10 border-purple-500/30',
  delivered: 'text-green-600 bg-green-500/10 border-green-500/30',
  cancelled: 'text-red-500 bg-red-500/10 border-red-500/30',
}
