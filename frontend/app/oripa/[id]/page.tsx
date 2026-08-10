'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
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

export default function OripaDetailPage() {
  const params = useParams()
  const id = Number(params?.id)
  const [oripa, setOripa] = useState<OripaPublic | null>(null)
  const [qty, setQty] = useState('1')
  const [labels, setLabels] = useState<string[]>([])
  const [buying, setBuying] = useState(false)

  useEffect(() => {
    if (!id) return
    void oripaApi
      .get(id)
      .then((res) => setOripa(res.data as OripaPublic))
      .catch(() => setOripa(null))
  }, [id])

  const purchase = async () => {
    setBuying(true)
    try {
      const key = `web-${id}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      const res = await oripaApi.purchase(id, { quantity: Number(qty), idempotency_key: key })
      const data = res.data as { entry_labels: string[]; quantity: number }
      setLabels(data.entry_labels || [])
      toast({ title: `${data.quantity}口購入しました` })
      const refreshed = await oripaApi.get(id)
      setOripa(refreshed.data as OripaPublic)
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
          {(oripa.sale_start_at || oripa.sale_end_at) && (
            <p data-testid="oripa-sale-period">
              販売期間:{' '}
              {oripa.sale_start_at ? new Date(oripa.sale_start_at).toLocaleString('ja-JP') : '開始未定'}
              {' 〜 '}
              {oripa.sale_end_at ? new Date(oripa.sale_end_at).toLocaleString('ja-JP') : '終了未定'}
            </p>
          )}
          <p className="text-amber-700">
            注意: 購入後に表示されるのは番号のみです。中身・当たり/ハズレは開封するまで分かりません。
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
          <Button type="button" data-testid="oripa-purchase-btn" disabled={buying || oripa.remaining_entries <= 0} onClick={() => void purchase()}>
            購入する
          </Button>
        </div>

        {labels.length > 0 && (
          <div className="mt-8 border rounded-lg p-4" data-testid="oripa-purchase-result">
            <p className="font-semibold mb-2">{labels.length}口購入しました</p>
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
