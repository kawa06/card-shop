'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@clerk/nextjs'
import { oripaApi } from '@/lib/api'

type Held = {
  id: number
  oripa_id: number
  oripa_title?: string | null
  entry_label: string
  shipment_status: string
  assigned_at?: string | null
}

export default function MyOripaPage() {
  const { isLoaded, isSignedIn } = useAuth()
  const [items, setItems] = useState<Held[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return
    void oripaApi
      .myEntries({ shipment_status: 'held', limit: 200 })
      .then((res) => setItems((res.data.items || []) as Held[]))
      .catch(() => setError('取得に失敗しました'))
  }, [isLoaded, isSignedIn])

  if (!isLoaded) return null
  if (!isSignedIn) {
    return (
      <div className="container py-8">
        <p>ログインが必要です</p>
        <Link href="/sign-in" className="underline">
          サインイン
        </Link>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-3xl">
        <h1 className="text-2xl font-bold mb-2" data-testid="mypage-oripa-heading">
          保管中オリパ
        </h1>
        <p className="text-sm text-gray-600 mb-6">番号のみ表示されます。中身は表示しません。</p>
        {error && <p className="text-red-600">{error}</p>}
        <div className="space-y-2" data-testid="mypage-oripa-list">
          {items.length === 0 ? (
            <p>保管中の番号はありません</p>
          ) : (
            items.map((item) => (
              <div key={item.id} className="border rounded p-3 flex justify-between" data-testid={`held-entry-${item.id}`}>
                <div>
                  <p className="font-semibold">{item.entry_label}</p>
                  <p className="text-xs text-gray-500">{item.oripa_title || `Oripa #${item.oripa_id}`}</p>
                </div>
                <p className="text-xs text-gray-500">{item.shipment_status}</p>
              </div>
            ))
          )}
        </div>
        <Link href="/oripa" className="underline text-sm mt-6 inline-block">
          オリパ一覧へ
        </Link>
      </div>
    </div>
  )
}
