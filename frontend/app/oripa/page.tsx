'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { oripaApi } from '@/lib/api'
import { Button } from '@/components/ui/button'

type OripaPublic = {
  id: number
  title: string
  description?: string | null
  price_per_entry: number
  total_entries: number
  remaining_entries: number
  status: string
  max_entries_per_purchase: number
}

export default function OripaListPage() {
  const [items, setItems] = useState<OripaPublic[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void oripaApi
      .list()
      .then((res) => setItems((res.data.items || []) as OripaPublic[]))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-4xl">
        <h1 className="text-2xl font-bold mb-2" data-testid="oripa-list-heading">
          オンラインオリパ
        </h1>
        <p className="text-sm text-gray-600 mb-6">
          購入時に番号のみが割り当てられます。中身は開封するまで分かりません。取得番号は保管し、後からまとめて発送できます。
        </p>
        {loading ? (
          <p>読み込み中...</p>
        ) : items.length === 0 ? (
          <p data-testid="oripa-list-empty">販売中のオリパはありません</p>
        ) : (
          <div className="space-y-4" data-testid="oripa-list">
            {items.map((item) => (
              <div key={item.id} className="border rounded-lg p-4" data-testid={`oripa-card-${item.id}`}>
                <h2 className="text-lg font-semibold">{item.title}</h2>
                <p className="text-sm text-gray-600 mt-1">
                  ¥{item.price_per_entry.toLocaleString()} / 口 · 残り {item.remaining_entries} / {item.total_entries}
                </p>
                <Button asChild className="mt-3" data-testid={`oripa-open-${item.id}`}>
                  <Link href={`/oripa/${item.id}`}>詳細・購入</Link>
                </Button>
              </div>
            ))}
          </div>
        )}
        <p className="mt-8 text-sm">
          <Link href="/mypage/oripa" className="underline" data-testid="oripa-mypage-link">
            保管中オリパを見る
          </Link>
        </p>
      </div>
    </div>
  )
}
