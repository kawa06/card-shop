'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminApi, adminInventoryApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

type RestockItem = {
  id: number
  product_id: number
  product_name?: string | null
  requested_quantity: number
  received_quantity?: number | null
  status: string
  note?: string | null
  created_at: string
  current_stock?: number | null
}

type CardOption = { id: number; name: string; stock: number }

export default function AdminInventoryRestocksPage() {
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const canRead = hasPermission('inventory_restock.read')
  const canWrite = hasPermission('inventory_restock.write')
  const [items, setItems] = useState<RestockItem[]>([])
  const [cards, setCards] = useState<CardOption[]>([])
  const [productId, setProductId] = useState('')
  const [qty, setQty] = useState('10')
  const [note, setNote] = useState('')
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  const reload = useCallback(async () => {
    if (!canRead) return
    setLoading(true)
    try {
      const res = await adminInventoryApi.listRestocks({
        status: status || undefined,
        sort: 'created_at',
        order: 'desc',
        limit: 100,
      })
      setItems(res.data.items || [])
    } catch {
      toast({ title: '補充一覧の取得に失敗しました', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [canRead, status])

  useEffect(() => {
    if (!isReady || !canRead) return
    void reload()
    void adminApi
      .getAllCards({ page: 1, per_page: 100 })
      .then((res) => {
        const data = res.data as { items?: CardOption[] } | CardOption[]
        const list = Array.isArray(data) ? data : data.items || []
        setCards(list.map((c) => ({ id: c.id, name: c.name, stock: c.stock })))
      })
      .catch(() => undefined)
  }, [isReady, canRead, reload])

  const create = async () => {
    if (!canWrite) return
    const pid = Number(productId)
    const requested = Number(qty)
    if (!pid || !requested) {
      toast({ title: '商品と数量を入力してください', variant: 'destructive' })
      return
    }
    try {
      await adminInventoryApi.createRestock({
        product_id: pid,
        requested_quantity: requested,
        note: note || undefined,
      })
      toast({ title: '補充リクエストを作成しました' })
      setNote('')
      await reload()
    } catch {
      toast({ title: '作成に失敗しました', variant: 'destructive' })
    }
  }

  const receive = async (id: number) => {
    if (!canWrite) return
    try {
      await adminInventoryApi.receiveRestock(id)
      toast({ title: '補充を受け取りました' })
      await reload()
    } catch {
      toast({ title: 'receive に失敗しました', variant: 'destructive' })
    }
  }

  if (!isReady) return null
  if (!canRead) {
    return <div className="container py-8">権限がありません</div>
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-6xl">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold" data-testid="inventory-restocks-heading">
            Inventory Restocks
          </h1>
          <Link href="/admin" className="text-sm underline text-gray-600">
            管理ホーム
          </Link>
        </div>

        {canWrite && (
          <div className="border rounded-lg p-4 mb-6 grid grid-cols-1 md:grid-cols-4 gap-3" data-testid="inventory-restock-create">
            <div>
              <Label>商品ID</Label>
              <Input data-testid="restock-product-id" value={productId} onChange={(e) => setProductId(e.target.value)} list="restock-card-options" />
              <datalist id="restock-card-options">
                {cards.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} (stock {c.stock})
                  </option>
                ))}
              </datalist>
            </div>
            <div>
              <Label>requested quantity</Label>
              <Input data-testid="restock-qty" value={qty} onChange={(e) => setQty(e.target.value)} />
            </div>
            <div>
              <Label>note</Label>
              <Input data-testid="restock-note" value={note} onChange={(e) => setNote(e.target.value)} />
            </div>
            <div className="flex items-end">
              <Button type="button" data-testid="restock-create-btn" onClick={() => void create()}>
                作成
              </Button>
            </div>
          </div>
        )}

        <div className="flex gap-2 mb-4">
          <Input data-testid="restock-status-filter" placeholder="status filter" value={status} onChange={(e) => setStatus(e.target.value)} className="max-w-xs" />
          <Button type="button" variant="outline" data-testid="restock-apply" onClick={() => void reload()} disabled={loading}>
            適用
          </Button>
        </div>

        <div className="overflow-x-auto border rounded-lg" data-testid="inventory-restocks-table">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left">ID</th>
                <th className="px-3 py-2 text-left">Product</th>
                <th className="px-3 py-2 text-left">Requested</th>
                <th className="px-3 py-2 text-left">Received</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Current stock</th>
                <th className="px-3 py-2 text-left">Created</th>
                <th className="px-3 py-2 text-left">Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-t" data-testid={`inventory-restock-row-${item.id}`}>
                  <td className="px-3 py-2">{item.id}</td>
                  <td className="px-3 py-2">{item.product_name || item.product_id}</td>
                  <td className="px-3 py-2">{item.requested_quantity}</td>
                  <td className="px-3 py-2">{item.received_quantity ?? '-'}</td>
                  <td className="px-3 py-2" data-testid={`restock-status-${item.id}`}>
                    {item.status}
                  </td>
                  <td className="px-3 py-2">{item.current_stock ?? '-'}</td>
                  <td className="px-3 py-2">{item.created_at}</td>
                  <td className="px-3 py-2">
                    {canWrite && (item.status === 'requested' || item.status === 'ordered') && (
                      <Button type="button" size="sm" data-testid={`restock-receive-${item.id}`} onClick={() => void receive(item.id)}>
                        Receive
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
