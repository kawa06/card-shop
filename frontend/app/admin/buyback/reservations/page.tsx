'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminBuybackApi } from '@/lib/api'
import type { BuybackStoreReservation } from '@/lib/types'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

function formatVisitAt(iso: string) {
  return new Date(iso).toLocaleString('ja-JP', {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function AdminBuybackReservationsPage() {
  const { isReady } = useAdminGuard()
  const [rows, setRows] = useState<BuybackStoreReservation[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')

  const load = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await adminBuybackApi.listReservations({
        from_date: fromDate || undefined,
        to_date: toDate || undefined,
      })
      setRows(res.data)
    } catch {
      toast({ title: '予約一覧の取得に失敗しました', variant: 'destructive' })
    } finally {
      setIsLoading(false)
    }
  }, [fromDate, toDate])

  useEffect(() => {
    if (isReady) void load()
  }, [isReady, load])

  if (!isReady) return null

  return (
    <div className="mx-auto max-w-5xl space-y-8 p-4 md:p-8">
      <div className="flex items-center gap-3">
        <Link href="/admin" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold">店舗買取予約</h1>
          <p className="text-sm text-muted-foreground">来店予約の確認</p>
        </div>
      </div>

      <div className="grid gap-4 rounded-xl border bg-card p-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label>開始日</Label>
          <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
        </div>
        <div className="space-y-2">
          <Label>終了日</Label>
          <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : rows.length === 0 ? (
        <p className="text-muted-foreground">予約がありません</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border">
          <table className="min-w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left">来店日時</th>
                <th className="px-4 py-3 text-left">申込番号</th>
                <th className="px-4 py-3 text-left">お客様</th>
                <th className="px-4 py-3 text-left">状態</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-t">
                  <td className="px-4 py-3 font-medium">{formatVisitAt(row.visit_at)}</td>
                  <td className="px-4 py-3">
                    {row.request_number ? (
                      <Link href={`/admin/buyback/requests/${row.request_id}`} className="text-primary underline">
                        {row.request_number}
                      </Link>
                    ) : (
                      `#${row.request_id}`
                    )}
                  </td>
                  <td className="px-4 py-3">{row.customer_name || `User #${row.user_id}`}</td>
                  <td className="px-4 py-3">{row.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
