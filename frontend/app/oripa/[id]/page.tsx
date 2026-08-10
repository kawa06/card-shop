'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams, useSearchParams } from 'next/navigation'
import { oripaApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

type OripaPublic = {
  id: number
  title: string
  description?: string | null
  price_per_entry: number
  total_entries: number
  remaining_entries: number
  max_entries_per_purchase: number
  status: string
  sale_start_at?: string | null
  sale_end_at?: string | null
}

type PurchaseResult = {
  purchase_id: number
  quantity: number
  entry_labels: string[]
  status: string
  checkout_url?: string | null
  payment_status?: string | null
  order_id?: number | null
}

export default function OripaDetailPage() {
  const params = useParams()
  const search = useSearchParams()
  const id = Number(params?.id)
  const [oripa, setOripa] = useState<OripaPublic | null>(null)
  const [qty, setQty] = useState('1')
  const [labels, setLabels] = useState<string[]>([])
  const [status, setStatus] = useState<string>('')
  const [buying, setBuying] = useState(false)

  useEffect(() => {
    if (!id) return
    void oripaApi
      .get(id)
      .then((res) => setOripa(res.data as OripaPublic))
      .catch(() => setOripa(null))
  }, [id])

  // After Stripe redirect back with purchase_id
  useEffect(() => {
    const purchaseId = Number(search?.get('purchase_id') || 0)
    if (!purchaseId) return
    let cancelled = false
    const poll = async () => {
      for (let i = 0; i < 20; i++) {
        try {
          const res = await oripaApi.getPurchase(purchaseId)
          const data = res.data as PurchaseResult
          if (cancelled) return
          setStatus(data.status)
          if (data.status === 'completed') {
            setLabels(data.entry_labels || [])
            toast({ title: `${data.quantity}口の決済が確定しました` })
            return
          }
          if (data.status === 'failed' || data.status === 'cancelled') {
            toast({ title: '決済に失敗またはキャンセルされました', variant: 'destructive' })
            return
          }
        } catch {
          /* keep polling */
        }
        await new Promise((r) => setTimeout(r, 1500))
      }
      if (!cancelled) setStatus('payment_processing')
    }
    void poll()
    return () => {
      cancelled = true
    }
  }, [search])

  const purchase = async () => {
    setBuying(true)
    setLabels([])
    setStatus('')
    try {
      const key = `web-${id}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      const res = await oripaApi.purchase(id, { quantity: Number(qty), idempotency_key: key })
      const data = res.data as PurchaseResult
      setStatus(data.status)
      if (data.checkout_url && data.status === 'pending') {
        toast({ title: '決済画面へ移動します' })
        window.location.href = data.checkout_url
        return
      }
      if (data.status === 'completed') {
        setLabels(data.entry_labels || [])
        toast({ title: `${data.quantity}口購入しました` })
        const refreshed = await oripaApi.get(id)
        setOripa(refreshed.data as OripaPublic)
      }
    } catch {
      toast({ title: '購入に失敗しました', variant: 'destructive' })
    } finally {
      setBuying(false)
    }
  }

  if (!oripa) {
    return <div className="container py-8">読み込み中...</div>
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-2xl">
        <Link href="/oripa" className="text-sm underline text-gray-600">
          一覧へ
        </Link>
        <h1 className="text-2xl font-bold mt-4" data-testid="oripa-detail-heading">
          {oripa.title}
        </h1>
        {oripa.description && <p className="text-sm text-gray-700 mt-2 whitespace-pre-wrap">{oripa.description}</p>}
        <div className="mt-4 space-y-1 text-sm" data-testid="oripa-detail-meta">
          <p>価格: ¥{oripa.price_per_entry.toLocaleString()} / 口</p>
          <p>
            口数: 残り {oripa.remaining_entries} / 全 {oripa.total_entries}
          </p>
          <p>1回あたり最大: {oripa.max_entries_per_purchase} 口</p>
          <p className="text-amber-700">
            注意: 決済完了後に番号のみ表示されます。中身・当たり/ハズレは開封するまで分かりません。
          </p>
        </div>

        <div className="mt-6 flex flex-wrap items-end gap-3" data-testid="oripa-purchase-form">
          <div>
            <Label>購入口数</Label>
            <Input
              data-testid="oripa-purchase-qty"
              type="number"
              min={1}
              max={oripa.max_entries_per_purchase}
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              className="w-28"
            />
          </div>
          <Button
            type="button"
            data-testid="oripa-purchase-btn"
            disabled={buying || oripa.remaining_entries <= 0}
            onClick={() => void purchase()}
          >
            {buying ? '処理中...' : '購入して決済へ'}
          </Button>
        </div>

        {status === 'pending' || status === 'payment_processing' ? (
          <div className="mt-6 text-sm text-blue-700" data-testid="oripa-payment-processing">
            決済処理中です。完了までお待ちください（Webhook 確定待ち）。
          </div>
        ) : null}

        {labels.length > 0 && (
          <div className="mt-8 border rounded-lg p-4" data-testid="oripa-purchase-result">
            <p className="font-semibold mb-2">{labels.length}口の決済が確定しました</p>
            <ul className="space-y-1">
              {labels.map((label) => (
                <li key={label} data-testid={`oripa-result-${label}`}>
                  {label}
                </li>
              ))}
            </ul>
            <p className="text-xs text-gray-500 mt-3">中身は表示されません。</p>
            <Link href="/mypage/oripa" className="underline text-sm mt-2 inline-block">
              保管中オリパへ
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
