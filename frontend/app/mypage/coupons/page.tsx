'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { couponsApi } from '@/lib/api'
import { useBackendAuth } from '@/hooks/useBackendAuth'

type UserCoupon = {
  id: number
  code: string
  name: string
  description?: string | null
  coupon_type: string
  amount_yen?: number | null
  percent_off?: number | null
  min_subtotal_yen: number
  remaining_uses_for_user?: number | null
  assigned: boolean
}

export default function MypageCouponsPage() {
  const { isLoggedIn, isReady, requireAuth } = useBackendAuth()
  const [items, setItems] = useState<UserCoupon[]>([])
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
        const res = await couponsApi.listMine()
        setItems(res.data.items || [])
      } catch {
        setItems([])
      } finally {
        setLoading(false)
      }
    })()
  }, [isReady, isLoggedIn, requireAuth])

  if (!isReady || !isLoggedIn) return null

  return (
    <div className="container py-8 max-w-2xl px-4">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold" data-testid="mypage-coupons-heading">
          クーポン
        </h1>
        <Link href="/mypage" className="text-sm text-blue-600">
          マイページへ
        </Link>
      </div>
      {loading ? (
        <p className="text-gray-500">読み込み中...</p>
      ) : items.length === 0 ? (
        <p className="text-gray-500" data-testid="mypage-coupons-empty">
          利用可能なクーポンはありません
        </p>
      ) : (
        <ul className="space-y-3" data-testid="mypage-coupons-list">
          {items.map((c) => (
            <li key={c.id} className="border rounded-lg p-4" data-testid={`mypage-coupon-${c.id}`}>
              <div className="font-semibold">
                {c.name} <span className="text-sm text-gray-500">({c.code})</span>
              </div>
              <div className="text-sm text-gray-600 mt-1">
                {c.coupon_type === 'fixed_amount' && `${(c.amount_yen || 0).toLocaleString()}円引き`}
                {c.coupon_type === 'percent' && `${c.percent_off}%オフ`}
                {c.coupon_type === 'free_shipping' && '送料無料'}
                {c.min_subtotal_yen > 0 ? ` · 最低購入 ${c.min_subtotal_yen.toLocaleString()}円` : ''}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                残り利用回数: {c.remaining_uses_for_user ?? '-'}
                {c.assigned ? ' · 配布クーポン' : ''}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
