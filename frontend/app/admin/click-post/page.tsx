'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Download, FileSpreadsheet, RefreshCw } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminApi } from '@/lib/api'
import { AdminClickPostOrder } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { toast } from '@/lib/use-toast'

function formatDateTime(iso: string) {
  const d = new Date(iso)
  return d.toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo' })
}

export default function AdminClickPostPage() {
  const { isReady } = useAdminGuard()
  const [orders, setOrders] = useState<AdminClickPostOrder[]>([])
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [isLoading, setIsLoading] = useState(true)
  const [isExporting, setIsExporting] = useState(false)
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const fetchOrders = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await adminApi.getClickPostOrders()
      setOrders(res.data || [])
      setSelected(new Set())
    } catch {
      toast({ title: 'エラー', description: '注文の取得に失敗しました', variant: 'destructive' })
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!isMounted || !isReady) return
    fetchOrders()
  }, [isMounted, isReady, fetchOrders])

  const allSelected = orders.length > 0 && selected.size === orders.length
  const selectedCount = selected.size

  const toggleAll = () => {
    if (allSelected) {
      setSelected(new Set())
    } else {
      setSelected(new Set(orders.map((o) => o.id)))
    }
  }

  const toggleOne = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const exportedCount = useMemo(
    () => orders.filter((o) => o.click_post_csv_exported_at).length,
    [orders]
  )

  const handleExport = async () => {
    if (selectedCount === 0) {
      toast({ title: '注文を選択してください', variant: 'destructive' })
      return
    }
    setIsExporting(true)
    try {
      const res = await adminApi.exportClickPostCsv(Array.from(selected), true)
      const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `click_post_orders_${new Date().toISOString().slice(0, 10)}.csv`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      toast({ title: 'CSVをダウンロードしました' })
      fetchOrders()
    } catch {
      toast({ title: 'エラー', description: 'CSV出力に失敗しました', variant: 'destructive' })
    } finally {
      setIsExporting(false)
    }
  }

  if (!isMounted || !isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-6 sm:py-8 max-w-6xl">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <Link href="/admin">
              <Button variant="ghost" size="icon" className="text-gray-400 hover:text-gray-900 shrink-0">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold text-gray-900 flex items-center gap-2">
                <FileSpreadsheet className="h-6 w-6 text-orange-400" />
                クリックポストCSV出力
              </h1>
              <p className="text-xs text-gray-500 mt-1">
                クリックポスト配送の注文を選択してCSV出力（UTF-8 BOM）
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={fetchOrders} disabled={isLoading}>
              <RefreshCw className={`h-4 w-4 mr-1 ${isLoading ? 'animate-spin' : ''}`} />
              更新
            </Button>
            <Button
              size="sm"
              className="bg-orange-500 hover:bg-orange-400 text-white"
              onClick={handleExport}
              disabled={isExporting || selectedCount === 0}
            >
              <Download className="h-4 w-4 mr-1" />
              {isExporting ? '出力中...' : `CSV出力 (${selectedCount})`}
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
            <p className="text-xs text-gray-500">クリックポスト注文</p>
            <p className="text-2xl font-bold text-gray-900">{orders.length}</p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
            <p className="text-xs text-gray-500">CSV出力済み</p>
            <p className="text-2xl font-bold text-green-600">{exportedCount}</p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 col-span-2 sm:col-span-1">
            <p className="text-xs text-gray-500">選択中</p>
            <p className="text-2xl font-bold text-orange-500">{selectedCount}</p>
          </div>
        </div>

        <div className="mb-3 flex items-center gap-2">
          <input
            type="checkbox"
            id="select-all"
            checked={allSelected}
            onChange={toggleAll}
            className="w-4 h-4 rounded border-gray-300 accent-orange-500"
          />
          <label htmlFor="select-all" className="text-sm text-gray-600 cursor-pointer">
            すべて選択
          </label>
        </div>

        {isLoading ? (
          <div className="p-12 text-center text-gray-400 animate-pulse">読み込み中...</div>
        ) : orders.length === 0 ? (
          <div className="p-12 text-center text-gray-400 border border-dashed border-gray-200 rounded-xl">
            クリックポストの注文はありません
          </div>
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden md:block overflow-x-auto rounded-xl border border-gray-200">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-500 text-left">
                  <tr>
                    <th className="p-3 w-10" />
                    <th className="p-3">注文番号</th>
                    <th className="p-3">購入者</th>
                    <th className="p-3">配送先</th>
                    <th className="p-3">商品</th>
                    <th className="p-3">注文日時</th>
                    <th className="p-3">状態</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((order) => (
                    <tr key={order.id} className="border-t border-gray-100 hover:bg-gray-50/50">
                      <td className="p-3">
                        <input
                          type="checkbox"
                          checked={selected.has(order.id)}
                          onChange={() => toggleOne(order.id)}
                          className="w-4 h-4 rounded border-gray-300 accent-orange-500"
                        />
                      </td>
                      <td className="p-3 font-mono font-medium">#{order.id}</td>
                      <td className="p-3">{order.buyer_name}</td>
                      <td className="p-3 text-xs text-gray-600 max-w-[200px]">
                        〒{order.postal_code}<br />
                        {order.region}{order.city}{order.address_line1}
                        {order.address_line2 && <><br />{order.address_line2}</>}
                      </td>
                      <td className="p-3 text-xs text-gray-600 max-w-[180px] truncate" title={order.product_names}>
                        {order.product_names}
                      </td>
                      <td className="p-3 text-xs whitespace-nowrap">{formatDateTime(order.created_at)}</td>
                      <td className="p-3">
                        {order.click_post_csv_exported_at ? (
                          <span className="inline-flex text-[10px] font-bold px-2 py-0.5 rounded-full bg-green-100 text-green-700">
                            CSV出力済み
                          </span>
                        ) : (
                          <span className="inline-flex text-[10px] font-bold px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">
                            未出力
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="md:hidden space-y-3">
              {orders.map((order) => (
                <label
                  key={order.id}
                  className={`block rounded-xl border p-4 cursor-pointer transition-colors ${
                    selected.has(order.id) ? 'border-orange-400 bg-orange-50/30' : 'border-gray-200 bg-gray-50'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={selected.has(order.id)}
                      onChange={() => toggleOne(order.id)}
                      className="mt-1 w-4 h-4 rounded border-gray-300 accent-orange-500 shrink-0"
                    />
                    <div className="min-w-0 flex-1 space-y-2">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-bold text-gray-900">#{order.id}</span>
                        {order.click_post_csv_exported_at ? (
                          <span className="shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-full bg-green-100 text-green-700">
                            CSV出力済み
                          </span>
                        ) : (
                          <span className="shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">
                            未出力
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-800">{order.buyer_name}</p>
                      <p className="text-xs text-gray-500 break-words">
                        〒{order.postal_code} {order.region}{order.city}{order.address_line1}
                        {order.address_line2 ? ` ${order.address_line2}` : ''}
                      </p>
                      <p className="text-xs text-gray-600 break-words">{order.product_names}</p>
                      <p className="text-[11px] text-gray-400">{formatDateTime(order.created_at)}</p>
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
