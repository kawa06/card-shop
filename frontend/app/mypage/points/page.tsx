'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useBackendAuth } from '@/hooks/useBackendAuth'
import { pointsApi } from '@/lib/api'

type Balance = {
  available_points: number
  reserved_points: number
  lifetime_earned: number
  lifetime_used: number
  expiring_soon_points: number
}

type Tx = {
  id: number
  type: string
  amount: number
  balance_after: number
  created_at: string
}

const TYPE_LABEL: Record<string, string> = {
  earn: '獲得',
  use: '利用',
  admin_grant: '付与',
  admin_deduct: '減算',
  cancel_restore: '返還',
  expire: '失効',
  adjustment: '調整',
}

export default function MypagePointsPage() {
  const { isLoggedIn, isReady, requireAuth } = useBackendAuth()
  const [balance, setBalance] = useState<Balance | null>(null)
  const [items, setItems] = useState<Tx[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isReady || !isLoggedIn) return
    void (async () => {
      setLoading(true)
      const token = await requireAuth()
      if (!token) {
        setLoading(false)
        return
      }
      try {
        const [b, h] = await Promise.all([
          pointsApi.getBalance(),
          pointsApi.getHistory({ limit: 50 }),
        ])
        setBalance(b.data)
        setItems(h.data.items || [])
      } finally {
        setLoading(false)
      }
    })()
  }, [isReady, isLoggedIn, requireAuth])

  if (!isReady || !isLoggedIn) return null

  return (
    <div className="container max-w-2xl py-8 px-4">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">ポイント</h1>
        <Link href="/mypage" className="text-sm text-blue-600 hover:underline">マイページへ</Link>
      </div>

      {loading ? (
        <p className="text-gray-500">読み込み中...</p>
      ) : (
        <>
          <section className="rounded-lg border bg-gradient-to-br from-yellow-50 to-white p-6 mb-6">
            <p className="text-sm text-gray-600 mb-1">利用可能ポイント</p>
            <p className="text-4xl font-bold text-gray-900">
              {(balance?.available_points ?? 0).toLocaleString()}
              <span className="text-lg ml-1">pt</span>
            </p>
            {balance && balance.expiring_soon_points > 0 && (
              <p className="text-sm text-amber-700 mt-2">
                30日以内に失効: {balance.expiring_soon_points.toLocaleString()}pt
              </p>
            )}
            <div className="grid grid-cols-2 gap-4 mt-4 text-sm text-gray-600">
              <div>生涯獲得: {balance?.lifetime_earned.toLocaleString()}pt</div>
              <div>生涯利用: {balance?.lifetime_used.toLocaleString()}pt</div>
            </div>
          </section>

          <section>
            <h2 className="font-semibold mb-3">ポイント履歴</h2>
            {items.length === 0 ? (
              <p className="text-gray-500 text-sm">履歴はありません</p>
            ) : (
              <ul className="divide-y border rounded-lg">
                {items.map((tx) => (
                  <li key={tx.id} className="p-4 flex justify-between items-start gap-4 text-sm">
                    <div>
                      <p className="font-medium">{TYPE_LABEL[tx.type] || tx.type}</p>
                      <p className="text-gray-500 text-xs">
                        {new Date(tx.created_at).toLocaleString('ja-JP')}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className={
                        tx.type === 'use' || tx.type === 'admin_deduct' || tx.type === 'expire'
                          ? 'text-red-600'
                          : 'text-green-700'
                      }>
                        {tx.type === 'use' || tx.type === 'admin_deduct' || tx.type === 'expire' ? '-' : '+'}
                        {tx.amount.toLocaleString()}pt
                      </p>
                      <p className="text-xs text-gray-400">残高 {tx.balance_after.toLocaleString()}pt</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  )
}
