'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { BarChart3 } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminAnalyticsApi, type AnalyticsDomain, type AnalyticsKpi, type AnalyticsList } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

const DOMAINS: Array<{ id: AnalyticsDomain; label: string }> = [
  { id: 'sales', label: '売上分析' },
  { id: 'live', label: 'ライブ分析' },
  { id: 'auctions', label: 'オークション分析' },
  { id: 'coupons', label: 'クーポン分析' },
  { id: 'points', label: 'ポイント分析' },
  { id: 'inventory', label: '在庫分析' },
]

export default function AdminAnalyticsPage() {
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const canRead = hasPermission('analytics.read')
  const canExport = hasPermission('analytics.export')

  const [domain, setDomain] = useState<AnalyticsDomain>('sales')
  const [kpi, setKpi] = useState<AnalyticsKpi | null>(null)
  const [list, setList] = useState<AnalyticsList | null>(null)
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [paymentStatus, setPaymentStatus] = useState('paid')
  const [shippingStatus, setShippingStatus] = useState('')
  const [sort, setSort] = useState('paid_at')
  const [order, setOrder] = useState<'asc' | 'desc'>('desc')
  const [fromAt, setFromAt] = useState('')
  const [toAt, setToAt] = useState('')
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)

  const reload = useCallback(async () => {
    if (!canRead) return
    setLoading(true)
    try {
      const params: Record<string, string | number> = {
        sort,
        order,
        page: 1,
        size: 50,
      }
      if (fromAt) params.from_at = fromAt
      if (toAt) params.to_at = toAt
      if (q.trim()) params.q = q.trim()
      if (domain === 'sales') {
        if (paymentStatus) params.payment_status = paymentStatus
        if (shippingStatus) params.shipping_status = shippingStatus
      } else if (status) {
        params.status = status
      }

      const [kpiRes, listRes] = await Promise.all([
        adminAnalyticsApi.kpi({ from_at: fromAt || undefined, to_at: toAt || undefined }),
        adminAnalyticsApi.list(domain, params),
      ])
      setKpi(kpiRes.data)
      setList(listRes.data)
    } catch {
      toast({ title: '分析データの取得に失敗しました', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [canRead, domain, fromAt, toAt, order, paymentStatus, q, shippingStatus, sort, status])

  useEffect(() => {
    if (!isReady || !canRead) return
    void reload()
  }, [isReady, canRead, reload])

  useEffect(() => {
    if (domain === 'sales') setSort('paid_at')
    else setSort('created_at')
  }, [domain])

  const onExport = async (format: 'csv' | 'xlsx' | 'pdf') => {
    if (!canExport) return
    setExporting(true)
    try {
      const params: Record<string, string> = { domain, format, sort, order }
      if (fromAt) params.from_at = fromAt
      if (toAt) params.to_at = toAt
      if (q.trim()) params.q = q.trim()
      if (domain === 'sales') {
        if (paymentStatus) params.payment_status = paymentStatus
        if (shippingStatus) params.shipping_status = shippingStatus
      } else if (status) {
        params.status = status
      }
      const res = await adminAnalyticsApi.export(params)
      const contentTypeHeader = res.headers['content-type']
      const contentType = typeof contentTypeHeader === 'string' ? contentTypeHeader : 'application/octet-stream'
      const blob = new Blob([res.data], { type: contentType })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `phase3-7-analytics-${domain}.${format}`
      a.click()
      URL.revokeObjectURL(url)
      toast({ title: `${format.toUpperCase()} を出力しました` })
      await reload()
    } catch {
      toast({ title: 'エクスポートに失敗しました', variant: 'destructive' })
    } finally {
      setExporting(false)
    }
  }

  if (!isReady) return null

  if (!canRead) {
    return (
      <div className="container py-8 max-w-5xl">
        <p className="text-sm text-gray-600">分析ダッシュボードを閲覧する権限がありません。</p>
        <Link href="/admin" className="text-sm text-blue-600 underline mt-2 inline-block">
          管理画面へ戻る
        </Link>
      </div>
    )
  }

  const columns = list?.items?.[0] ? Object.keys(list.items[0] as Record<string, unknown>) : []

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-6xl">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
          <div className="flex items-center gap-3">
            <BarChart3 className="h-6 w-6 text-yellow-500" />
            <h1 className="text-2xl font-bold text-gray-900" data-testid="admin-analytics-heading">
              分析ダッシュボード
            </h1>
          </div>
          <Link href="/admin" className="text-sm text-gray-600 underline">
            管理ホーム
          </Link>
        </div>

        {kpi && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6" data-testid="admin-analytics-kpi">
            {[
              { label: '売上合計', value: `¥${kpi.paid_sales_yen.toLocaleString('ja-JP')}` },
              { label: '支払済注文', value: kpi.paid_order_count },
              { label: '平均単価', value: `¥${kpi.avg_order_yen.toLocaleString('ja-JP')}` },
              { label: 'クーポン値引', value: `¥${kpi.coupon_discount_yen.toLocaleString('ja-JP')}` },
              { label: '利用ポイント', value: kpi.points_used },
              { label: '付与ポイント', value: kpi.points_earned },
              { label: 'ライブ数', value: kpi.live_stream_count },
              { label: '配信中', value: kpi.live_live_count },
              { label: 'オークション', value: kpi.auction_count },
              { label: '落札GMV', value: `¥${kpi.auction_gmv_yen.toLocaleString('ja-JP')}` },
              { label: 'Low Stock', value: kpi.low_stock_products ?? 0 },
              { label: 'Out of Stock', value: kpi.out_of_stock_products ?? 0 },
              { label: 'Pending Restocks', value: kpi.pending_restocks ?? 0 },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-lg border bg-gray-50 px-4 py-3">
                <p className="text-xs text-gray-500">{label}</p>
                <p className="text-lg font-bold text-gray-900 mt-1">{value}</p>
              </div>
            ))}
          </div>
        )}

        <div className="flex flex-wrap gap-2 mb-4" data-testid="admin-analytics-domain-tabs">
          {DOMAINS.map((d) => (
            <Button
              key={d.id}
              type="button"
              variant={domain === d.id ? 'default' : 'outline'}
              data-testid={`analytics-domain-${d.id}`}
              onClick={() => setDomain(d.id)}
            >
              {d.label}
            </Button>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-4" data-testid="admin-analytics-filters">
          <div>
            <Label htmlFor="analytics-q">検索</Label>
            <Input id="analytics-q" data-testid="analytics-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="注文番号 / コード / タイトル" />
          </div>
          <div>
            <Label htmlFor="analytics-from">開始日時</Label>
            <Input id="analytics-from" data-testid="analytics-from" type="datetime-local" value={fromAt} onChange={(e) => setFromAt(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="analytics-to">終了日時</Label>
            <Input id="analytics-to" data-testid="analytics-to" type="datetime-local" value={toAt} onChange={(e) => setToAt(e.target.value)} />
          </div>
          {domain === 'sales' ? (
            <>
              <div>
                <Label htmlFor="analytics-payment">支払ステータス</Label>
                <Input id="analytics-payment" data-testid="analytics-payment-status" value={paymentStatus} onChange={(e) => setPaymentStatus(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="analytics-shipping">配送ステータス</Label>
                <Input id="analytics-shipping" data-testid="analytics-shipping-status" value={shippingStatus} onChange={(e) => setShippingStatus(e.target.value)} />
              </div>
            </>
          ) : (
            <div>
              <Label htmlFor="analytics-status">ステータス / 種別</Label>
              <Input id="analytics-status" data-testid="analytics-status" value={status} onChange={(e) => setStatus(e.target.value)} />
            </div>
          )}
          <div>
            <Label htmlFor="analytics-sort">並び替え</Label>
            <Input id="analytics-sort" data-testid="analytics-sort" value={sort} onChange={(e) => setSort(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="analytics-order">順序</Label>
            <select
              id="analytics-order"
              data-testid="analytics-order"
              className="w-full h-10 rounded-md border px-3 text-sm"
              value={order}
              onChange={(e) => setOrder(e.target.value as 'asc' | 'desc')}
            >
              <option value="desc">降順</option>
              <option value="asc">昇順</option>
            </select>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 mb-4">
          <Button type="button" data-testid="analytics-apply-filters" onClick={() => void reload()} disabled={loading}>
            {loading ? '読込中...' : '適用'}
          </Button>
          {canExport && (
            <>
              <Button type="button" variant="outline" data-testid="analytics-export-csv" disabled={exporting} onClick={() => void onExport('csv')}>
                CSV
              </Button>
              <Button type="button" variant="outline" data-testid="analytics-export-xlsx" disabled={exporting} onClick={() => void onExport('xlsx')}>
                Excel
              </Button>
              <Button type="button" variant="outline" data-testid="analytics-export-pdf" disabled={exporting} onClick={() => void onExport('pdf')}>
                PDF
              </Button>
            </>
          )}
        </div>

        <div className="overflow-x-auto rounded-lg border" data-testid="admin-analytics-table">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                {columns.map((col) => (
                  <th key={col} className="px-3 py-2 text-left font-medium text-gray-600 whitespace-nowrap">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(list?.items || []).map((row, idx) => {
                const record = row as Record<string, unknown>
                const key = String(record.order_id ?? record.stream_id ?? record.auction_id ?? record.coupon_id ?? record.transaction_id ?? idx)
                return (
                  <tr key={key} className="border-t" data-testid={`analytics-row-${key}`}>
                    {columns.map((col) => (
                      <td key={col} className="px-3 py-2 whitespace-nowrap text-gray-800">
                        {record[col] == null ? '' : String(record[col])}
                      </td>
                    ))}
                  </tr>
                )
              })}
              {!loading && (list?.items?.length || 0) === 0 && (
                <tr>
                  <td className="px-3 py-6 text-gray-500" colSpan={Math.max(columns.length, 1)}>
                    データがありません
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {list && (
          <p className="text-xs text-gray-500 mt-2" data-testid="admin-analytics-total">
            件数: {list.total} / page {list.page} / sort {list.sort} {list.order}
          </p>
        )}
      </div>
    </div>
  )
}
