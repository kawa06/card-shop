'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminInventoryApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

type AlertItem = {
  id: number
  product_id: number
  product_name?: string | null
  alert_type: string
  stock_quantity: number
  threshold: number
  status: string
  created_at: string
  resolved_at?: string | null
}

export default function AdminInventoryAlertsPage() {
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const canRead = hasPermission('inventory_alert.read')
  const canWrite = hasPermission('inventory_alert.write')
  const [items, setItems] = useState<AlertItem[]>([])
  const [total, setTotal] = useState(0)
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('open')
  const [alertType, setAlertType] = useState('')
  const [loading, setLoading] = useState(false)

  const reload = useCallback(async () => {
    if (!canRead) return
    setLoading(true)
    try {
      const res = await adminInventoryApi.listAlerts({
        q: q || undefined,
        status: status || undefined,
        alert_type: alertType || undefined,
        sort: 'created_at',
        order: 'desc',
        limit: 100,
      })
      setItems(res.data.items || [])
      setTotal(res.data.total || 0)
    } catch {
      toast({ title: 'アラート取得に失敗しました', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [alertType, canRead, q, status])

  useEffect(() => {
    if (!isReady || !canRead) return
    void reload()
  }, [isReady, canRead, reload])

  const resolve = async (id: number) => {
    if (!canWrite) return
    try {
      await adminInventoryApi.resolveAlert(id)
      toast({ title: 'アラートを解決しました' })
      await reload()
    } catch {
      toast({ title: '解決に失敗しました', variant: 'destructive' })
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
          <h1 className="text-2xl font-bold" data-testid="inventory-alerts-heading">
            Inventory Alerts
          </h1>
          <Link href="/admin" className="text-sm underline text-gray-600">
            管理ホーム
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4" data-testid="inventory-alerts-filters">
          <div>
            <Label>検索</Label>
            <Input data-testid="inventory-alerts-search" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div>
            <Label>status</Label>
            <Input data-testid="inventory-alerts-status" value={status} onChange={(e) => setStatus(e.target.value)} />
          </div>
          <div>
            <Label>alert type</Label>
            <Input data-testid="inventory-alerts-type" value={alertType} onChange={(e) => setAlertType(e.target.value)} />
          </div>
          <div className="flex items-end">
            <Button type="button" data-testid="inventory-alerts-apply" onClick={() => void reload()} disabled={loading}>
              適用
            </Button>
          </div>
        </div>

        <div className="overflow-x-auto border rounded-lg" data-testid="inventory-alerts-table">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left">ID</th>
                <th className="px-3 py-2 text-left">Product</th>
                <th className="px-3 py-2 text-left">Stock</th>
                <th className="px-3 py-2 text-left">Threshold</th>
                <th className="px-3 py-2 text-left">Type</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Created</th>
                <th className="px-3 py-2 text-left">Resolved</th>
                <th className="px-3 py-2 text-left">Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-t" data-testid={`inventory-alert-row-${item.id}`}>
                  <td className="px-3 py-2">{item.id}</td>
                  <td className="px-3 py-2">
                    {item.product_name || item.product_id}
                  </td>
                  <td className="px-3 py-2">{item.stock_quantity}</td>
                  <td className="px-3 py-2">{item.threshold}</td>
                  <td className="px-3 py-2">{item.alert_type}</td>
                  <td className="px-3 py-2">{item.status}</td>
                  <td className="px-3 py-2">{item.created_at}</td>
                  <td className="px-3 py-2">{item.resolved_at || '-'}</td>
                  <td className="px-3 py-2">
                    {canWrite && item.status === 'open' && (
                      <Button type="button" size="sm" data-testid={`inventory-alert-resolve-${item.id}`} onClick={() => void resolve(item.id)}>
                        Resolve
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-gray-500 mt-2" data-testid="inventory-alerts-total">
          件数: {total}
        </p>
      </div>
    </div>
  )
}
