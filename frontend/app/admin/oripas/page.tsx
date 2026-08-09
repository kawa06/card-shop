'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminOripaApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

type OripaItem = {
  id: number
  title: string
  price_per_entry: number
  total_entries: number
  status: string
  available_entries?: number
  assigned_entries?: number
  linked_entries?: number
}

export default function AdminOripaListPage() {
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const canRead = hasPermission('oripa.read')
  const canCreate = hasPermission('oripa.create')
  const [items, setItems] = useState<OripaItem[]>([])
  const [title, setTitle] = useState('')
  const [price, setPrice] = useState('1000')
  const [total, setTotal] = useState('10')
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  const reload = useCallback(async () => {
    if (!canRead) return
    setLoading(true)
    try {
      const res = await adminOripaApi.list({ status: status || undefined, limit: 100 })
      setItems((res.data.items || []) as OripaItem[])
    } catch {
      toast({ title: 'オリパ一覧の取得に失敗しました', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [canRead, status])

  useEffect(() => {
    if (!isReady || !canRead) return
    void reload()
  }, [isReady, canRead, reload])

  const create = async () => {
    if (!canCreate) return
    try {
      const res = await adminOripaApi.create({
        title,
        price_per_entry: Number(price),
        total_entries: Number(total),
        max_entries_per_purchase: 10,
        status: 'draft',
      })
      toast({ title: 'オリパを作成しました' })
      setTitle('')
      await reload()
      const id = (res.data as { id: number }).id
      if (id) window.location.href = `/admin/oripas/${id}`
    } catch {
      toast({ title: '作成に失敗しました', variant: 'destructive' })
    }
  }

  if (!isReady) return null
  if (!canRead) return <div className="container py-8">権限がありません</div>

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-6xl">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold" data-testid="admin-oripas-heading">
            Oripa
          </h1>
          <Link href="/admin" className="text-sm underline text-gray-600">
            管理ホーム
          </Link>
        </div>

        {canCreate && (
          <div className="border rounded-lg p-4 mb-6 grid grid-cols-1 md:grid-cols-4 gap-3" data-testid="oripa-create-form">
            <div>
              <Label>タイトル</Label>
              <Input data-testid="oripa-title" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div>
              <Label>price / entry</Label>
              <Input data-testid="oripa-price" value={price} onChange={(e) => setPrice(e.target.value)} />
            </div>
            <div>
              <Label>total entries</Label>
              <Input data-testid="oripa-total" value={total} onChange={(e) => setTotal(e.target.value)} />
            </div>
            <div className="flex items-end">
              <Button type="button" data-testid="oripa-create-btn" onClick={() => void create()}>
                作成
              </Button>
            </div>
          </div>
        )}

        <div className="flex gap-2 mb-4">
          <Input
            data-testid="oripa-status-filter"
            placeholder="status filter"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="max-w-xs"
          />
          <Button type="button" variant="outline" onClick={() => void reload()} disabled={loading}>
            適用
          </Button>
        </div>

        <div className="overflow-x-auto border rounded-lg" data-testid="oripa-table">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left">ID</th>
                <th className="px-3 py-2 text-left">Title</th>
                <th className="px-3 py-2 text-left">Price</th>
                <th className="px-3 py-2 text-left">Entries</th>
                <th className="px-3 py-2 text-left">Available</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-t" data-testid={`oripa-row-${item.id}`}>
                  <td className="px-3 py-2">{item.id}</td>
                  <td className="px-3 py-2">{item.title}</td>
                  <td className="px-3 py-2">¥{item.price_per_entry}</td>
                  <td className="px-3 py-2">{item.total_entries}</td>
                  <td className="px-3 py-2">{item.available_entries ?? '-'}</td>
                  <td className="px-3 py-2">{item.status}</td>
                  <td className="px-3 py-2">
                    <Link href={`/admin/oripas/${item.id}`} className="underline" data-testid={`oripa-open-${item.id}`}>
                      詳細
                    </Link>
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
