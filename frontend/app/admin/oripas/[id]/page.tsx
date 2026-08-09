'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminOripaApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

type OripaDetail = {
  id: number
  title: string
  description?: string | null
  price_per_entry: number
  total_entries: number
  status: string
  available_entries?: number
  assigned_entries?: number
  linked_entries?: number
  max_entries_per_purchase: number
}

type EntryItem = {
  id: number
  entry_number: number
  entry_label: string
  linked_product_id?: number | null
  linked_product_name?: string | null
  assignment_status: string
  shipment_status: string
}

export default function AdminOripaDetailPage() {
  const params = useParams()
  const oripaId = Number(params?.id)
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const canRead = hasPermission('oripa.read')
  const canUpdate = hasPermission('oripa.update')
  const canManageEntries = hasPermission('oripa_entry.manage')
  const canReadEntries = hasPermission('oripa_entry.read')
  const [oripa, setOripa] = useState<OripaDetail | null>(null)
  const [entries, setEntries] = useState<EntryItem[]>([])
  const [linkEntryId, setLinkEntryId] = useState('')
  const [linkProductId, setLinkProductId] = useState('')

  const reload = useCallback(async () => {
    if (!canRead || !oripaId) return
    try {
      const [o, e] = await Promise.all([
        adminOripaApi.get(oripaId),
        canReadEntries ? adminOripaApi.listEntries(oripaId, { limit: 500 }) : Promise.resolve(null),
      ])
      setOripa(o.data as OripaDetail)
      if (e) setEntries((((e.data as unknown) as { items: EntryItem[] }).items || []) as EntryItem[])
    } catch {
      toast({ title: '読み込みに失敗しました', variant: 'destructive' })
    }
  }, [canRead, canReadEntries, oripaId])

  useEffect(() => {
    if (!isReady) return
    void reload()
  }, [isReady, reload])

  const generate = async () => {
    if (!canManageEntries) return
    try {
      await adminOripaApi.generateEntries(oripaId)
      toast({ title: '番号を生成しました' })
      await reload()
    } catch {
      toast({ title: '番号生成に失敗しました', variant: 'destructive' })
    }
  }

  const publish = async () => {
    if (!canUpdate) return
    try {
      await adminOripaApi.update(oripaId, { status: 'on_sale' })
      toast({ title: '販売中にしました' })
      await reload()
    } catch {
      toast({ title: '公開に失敗しました', variant: 'destructive' })
    }
  }

  const endSale = async () => {
    if (!canUpdate) return
    try {
      await adminOripaApi.update(oripaId, { status: 'ended' })
      toast({ title: '販売終了にしました' })
      await reload()
    } catch {
      toast({ title: '終了に失敗しました', variant: 'destructive' })
    }
  }

  const link = async () => {
    if (!canManageEntries) return
    try {
      await adminOripaApi.linkEntry(Number(linkEntryId), {
        linked_product_id: Number(linkProductId),
      })
      toast({ title: '商品を紐付けました' })
      await reload()
    } catch {
      toast({ title: '紐付けに失敗しました', variant: 'destructive' })
    }
  }

  if (!isReady) return null
  if (!canRead) return <div className="container py-8">権限がありません</div>
  if (!oripa) return <div className="container py-8">読み込み中...</div>

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-6xl">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold" data-testid="admin-oripa-detail-heading">
            {oripa.title}
          </h1>
          <Link href="/admin/oripas" className="text-sm underline text-gray-600">
            一覧へ
          </Link>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6" data-testid="oripa-detail-kpis">
          <div className="border rounded p-3">
            <p className="text-xs text-gray-500">Status</p>
            <p className="font-bold">{oripa.status}</p>
          </div>
          <div className="border rounded p-3">
            <p className="text-xs text-gray-500">Price</p>
            <p className="font-bold">¥{oripa.price_per_entry}</p>
          </div>
          <div className="border rounded p-3">
            <p className="text-xs text-gray-500">Available</p>
            <p className="font-bold">{oripa.available_entries ?? 0}</p>
          </div>
          <div className="border rounded p-3">
            <p className="text-xs text-gray-500">Assigned</p>
            <p className="font-bold">{oripa.assigned_entries ?? 0}</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 mb-6">
          {canManageEntries && (
            <Button type="button" data-testid="oripa-generate-entries" onClick={() => void generate()}>
              番号生成
            </Button>
          )}
          {canUpdate && (
            <>
              <Button type="button" variant="outline" data-testid="oripa-publish" onClick={() => void publish()}>
                公開 (on_sale)
              </Button>
              <Button type="button" variant="outline" data-testid="oripa-end" onClick={() => void endSale()}>
                販売終了
              </Button>
            </>
          )}
        </div>

        {canManageEntries && (
          <div className="border rounded-lg p-4 mb-6 grid grid-cols-1 md:grid-cols-3 gap-3" data-testid="oripa-link-form">
            <div>
              <Label>entry id</Label>
              <Input data-testid="oripa-link-entry-id" value={linkEntryId} onChange={(e) => setLinkEntryId(e.target.value)} />
            </div>
            <div>
              <Label>product id</Label>
              <Input data-testid="oripa-link-product-id" value={linkProductId} onChange={(e) => setLinkProductId(e.target.value)} />
            </div>
            <div className="flex items-end">
              <Button type="button" data-testid="oripa-link-btn" onClick={() => void link()}>
                商品紐付け
              </Button>
            </div>
          </div>
        )}

        {canReadEntries && (
          <div className="overflow-x-auto border rounded-lg" data-testid="oripa-entries-table">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left">Entry</th>
                  <th className="px-3 py-2 text-left">Product</th>
                  <th className="px-3 py-2 text-left">Assignment</th>
                  <th className="px-3 py-2 text-left">Shipment</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.id} className="border-t" data-testid={`oripa-entry-row-${e.id}`}>
                    <td className="px-3 py-2">
                      {e.entry_label} (id {e.id})
                    </td>
                    <td className="px-3 py-2">
                      {e.linked_product_name || e.linked_product_id || '-'}
                    </td>
                    <td className="px-3 py-2">{e.assignment_status}</td>
                    <td className="px-3 py-2">{e.shipment_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
