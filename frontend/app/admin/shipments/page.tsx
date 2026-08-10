'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { adminShipmentsApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

type Shipment = {
  id: number
  user_id: number
  status: string
  tracking_number?: string | null
  entry_labels: string[]
  items: Array<{ oripa_entry_id?: number; entry_label?: string; linked_product_name?: string }>
}

export default function AdminShipmentsPage() {
  const [items, setItems] = useState<Shipment[]>([])
  const [userId, setUserId] = useState('')
  const [entryIds, setEntryIds] = useState('')
  const [selected, setSelected] = useState<Shipment | null>(null)
  const [tracking, setTracking] = useState('')

  const reload = () => {
    void adminShipmentsApi.list({ limit: 50 }).then((res) => setItems((res.data.items || []) as Shipment[]))
  }

  useEffect(() => {
    reload()
  }, [])

  const create = async () => {
    try {
      const ids = entryIds
        .split(/[,\s]+/)
        .map((s) => Number(s.trim()))
        .filter((n) => Number.isFinite(n) && n > 0)
      const res = await adminShipmentsApi.create({
        user_id: Number(userId),
        entry_ids: ids,
      })
      toast({ title: `Shipment #${(res.data as { id: number }).id} 作成` })
      setEntryIds('')
      reload()
    } catch {
      toast({ title: '作成に失敗しました', variant: 'destructive' })
    }
  }

  const markShipped = async (id: number) => {
    try {
      await adminShipmentsApi.update(id, {
        status: 'shipped',
        tracking_number: tracking || undefined,
        shipping_carrier: 'yamato',
      })
      toast({ title: '発送済みに更新しました' })
      reload()
      const detail = await adminShipmentsApi.get(id)
      setSelected(detail.data as Shipment)
    } catch {
      toast({ title: '更新に失敗しました', variant: 'destructive' })
    }
  }

  return (
    <div className="container py-8 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold" data-testid="admin-shipments-heading">
          オリパ発送 (Shipment)
        </h1>
        <Link href="/admin/oripas" className="text-sm underline">
          オリパ管理へ
        </Link>
      </div>

      <div className="border rounded-lg p-4 mb-8 space-y-3" data-testid="admin-shipment-create">
        <p className="text-sm text-gray-600">保管中の entry id を指定して Shipment を作成（単体 / 複数オリパ対応）</p>
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <Label>user_id</Label>
            <Input data-testid="shipment-user-id" value={userId} onChange={(e) => setUserId(e.target.value)} className="w-28" />
          </div>
          <div className="flex-1 min-w-[200px]">
            <Label>entry_ids (comma)</Label>
            <Input data-testid="shipment-entry-ids" value={entryIds} onChange={(e) => setEntryIds(e.target.value)} />
          </div>
          <Button type="button" data-testid="shipment-create-btn" onClick={() => void create()}>
            作成
          </Button>
        </div>
      </div>

      <div className="space-y-3" data-testid="admin-shipments-list">
        {items.map((s) => (
          <div key={s.id} className="border rounded p-3 flex flex-wrap justify-between gap-2">
            <div>
              <button type="button" className="font-semibold underline" data-testid={`shipment-open-${s.id}`} onClick={() => setSelected(s)}>
                Shipment #{s.id}
              </button>
              <p className="text-xs text-gray-500">
                user={s.user_id} · {s.status} · {s.entry_labels?.join(', ')}
              </p>
            </div>
            <Button
              type="button"
              size="sm"
              variant="outline"
              data-testid={`shipment-ship-${s.id}`}
              onClick={() => void markShipped(s.id)}
            >
              発送済み
            </Button>
          </div>
        ))}
      </div>

      {selected && (
        <div className="mt-8 border rounded p-4" data-testid="admin-shipment-detail">
          <h2 className="font-semibold mb-2">Shipment #{selected.id}</h2>
          <p className="text-sm mb-2">番号: {selected.entry_labels?.join(', ')}</p>
          <ul className="text-sm space-y-1 mb-3">
            {selected.items?.map((it) => (
              <li key={it.oripa_entry_id}>
                {it.entry_label} → {it.linked_product_name || '(未紐付)'}
              </li>
            ))}
          </ul>
          <div className="flex gap-2 items-end">
            <div>
              <Label>tracking</Label>
              <Input value={tracking} onChange={(e) => setTracking(e.target.value)} className="w-48" data-testid="shipment-tracking" />
            </div>
            <Button type="button" onClick={() => void markShipped(selected.id)}>
              tracking付き発送
            </Button>
          </div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            className="mt-4 border"
            alt="barcode"
            src={`/api/admin/shipments/${selected.id}/barcode.svg`}
            data-testid="shipment-barcode-img"
          />
        </div>
      )}
    </div>
  )
}
