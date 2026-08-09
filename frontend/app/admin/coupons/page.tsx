'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { adminCouponsApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

type Coupon = {
  id: number
  code: string
  name: string
  coupon_type: string
  audience: string
  amount_yen?: number | null
  percent_off?: number | null
  max_discount_yen?: number | null
  min_subtotal_yen: number
  max_uses_total?: number | null
  max_uses_per_user: number
  is_active: boolean
  redemption_count: number
}

export default function AdminCouponsPage() {
  const [items, setItems] = useState<Coupon[]>([])
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [couponType, setCouponType] = useState<'fixed_amount' | 'percent' | 'free_shipping'>('fixed_amount')
  const [amountYen, setAmountYen] = useState('500')
  const [percentOff, setPercentOff] = useState('10')
  const [minSubtotal, setMinSubtotal] = useState('0')
  const [maxUsesTotal, setMaxUsesTotal] = useState('')
  const [maxUsesPerUser, setMaxUsesPerUser] = useState('1')
  const [audience, setAudience] = useState<'public' | 'assigned'>('public')
  const [assignCouponId, setAssignCouponId] = useState('')
  const [assignUserId, setAssignUserId] = useState('')
  const [loading, setLoading] = useState(false)

  const reload = async () => {
    const res = await adminCouponsApi.list({ limit: 100 })
    setItems(res.data.items || [])
  }

  useEffect(() => {
    void reload().catch(() => undefined)
  }, [])

  const createCoupon = async () => {
    if (!code.trim() || !name.trim()) {
      toast({ title: '入力エラー', variant: 'destructive' })
      return
    }
    setLoading(true)
    try {
      await adminCouponsApi.create({
        code: code.trim(),
        name: name.trim(),
        coupon_type: couponType,
        audience,
        amount_yen: couponType === 'fixed_amount' ? Number(amountYen) : null,
        percent_off: couponType === 'percent' ? Number(percentOff) : null,
        min_subtotal_yen: Number(minSubtotal) || 0,
        max_uses_total: maxUsesTotal ? Number(maxUsesTotal) : null,
        max_uses_per_user: Number(maxUsesPerUser) || 1,
        is_active: true,
      })
      toast({ title: 'クーポンを作成しました' })
      setCode('')
      setName('')
      await reload()
    } catch (e: any) {
      toast({ title: 'エラー', description: e?.response?.data?.detail || '作成に失敗', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }

  const assign = async () => {
    const couponId = parseInt(assignCouponId, 10)
    const userId = parseInt(assignUserId, 10)
    if (!couponId || !userId) {
      toast({ title: '入力エラー', variant: 'destructive' })
      return
    }
    try {
      await adminCouponsApi.assign(couponId, { user_id: userId })
      toast({ title: 'クーポンを配布しました' })
      await reload()
    } catch (e: any) {
      toast({ title: 'エラー', description: e?.response?.data?.detail || '配布に失敗', variant: 'destructive' })
    }
  }

  const exportCsv = async () => {
    try {
      const res = await adminCouponsApi.exportCsv()
      const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'coupons.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      toast({ title: 'エラー', description: e?.response?.data?.detail || 'CSV出力に失敗', variant: 'destructive' })
    }
  }

  return (
    <div className="container py-8 max-w-4xl">
      <div className="flex items-center gap-4 mb-6">
        <Link href="/admin" className="text-sm text-blue-600">
          ← 管理画面
        </Link>
        <h1 className="text-2xl font-bold" data-testid="admin-coupons-heading">
          クーポン管理
        </h1>
      </div>

      <section className="border rounded-lg p-5 mb-8 space-y-4">
        <h2 className="font-semibold">新規クーポン</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <Label>コード</Label>
            <Input data-testid="coupon-code-input" value={code} onChange={(e) => setCode(e.target.value)} />
          </div>
          <div>
            <Label>名称</Label>
            <Input data-testid="coupon-name-input" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <Label>種別</Label>
            <select
              data-testid="coupon-type-select"
              className="w-full h-10 border rounded-md px-3"
              value={couponType}
              onChange={(e) => setCouponType(e.target.value as any)}
            >
              <option value="fixed_amount">固定金額</option>
              <option value="percent">割引率</option>
              <option value="free_shipping">送料無料</option>
            </select>
          </div>
          <div>
            <Label>配布対象</Label>
            <select
              className="w-full h-10 border rounded-md px-3"
              value={audience}
              onChange={(e) => setAudience(e.target.value as any)}
            >
              <option value="public">公開コード</option>
              <option value="assigned">特定ユーザー</option>
            </select>
          </div>
          {couponType === 'fixed_amount' && (
            <div>
              <Label>割引額（円）</Label>
              <Input type="number" value={amountYen} onChange={(e) => setAmountYen(e.target.value)} />
            </div>
          )}
          {couponType === 'percent' && (
            <div>
              <Label>割引率（%）</Label>
              <Input type="number" value={percentOff} onChange={(e) => setPercentOff(e.target.value)} />
            </div>
          )}
          <div>
            <Label>最低購入金額</Label>
            <Input type="number" value={minSubtotal} onChange={(e) => setMinSubtotal(e.target.value)} />
          </div>
          <div>
            <Label>全体利用上限（空=無制限）</Label>
            <Input type="number" value={maxUsesTotal} onChange={(e) => setMaxUsesTotal(e.target.value)} />
          </div>
          <div>
            <Label>1人あたり上限</Label>
            <Input type="number" value={maxUsesPerUser} onChange={(e) => setMaxUsesPerUser(e.target.value)} />
          </div>
        </div>
        <Button data-testid="coupon-create-button" onClick={() => void createCoupon()} disabled={loading}>
          作成
        </Button>
      </section>

      <section className="border rounded-lg p-5 mb-8 space-y-3">
        <h2 className="font-semibold">ユーザー配布</h2>
        <div className="flex flex-wrap gap-2">
          <Input
            placeholder="クーポンID"
            value={assignCouponId}
            onChange={(e) => setAssignCouponId(e.target.value)}
            className="w-40"
          />
          <Input
            placeholder="ユーザーID"
            data-testid="coupon-assign-user-id"
            value={assignUserId}
            onChange={(e) => setAssignUserId(e.target.value)}
            className="w-40"
          />
          <Button type="button" variant="outline" onClick={() => void assign()}>
            配布
          </Button>
          <Button type="button" variant="outline" data-testid="coupon-export-csv" onClick={() => void exportCsv()}>
            CSV出力
          </Button>
        </div>
      </section>

      <section className="border rounded-lg p-5">
        <h2 className="font-semibold mb-3">クーポン一覧</h2>
        <ul className="space-y-2" data-testid="admin-coupons-list">
          {items.map((c) => (
            <li key={c.id} className="border rounded-md p-3 text-sm" data-testid={`admin-coupon-${c.id}`}>
              <div className="font-medium">
                #{c.id} {c.code} / {c.name}
              </div>
              <div className="text-gray-600">
                {c.coupon_type} · {c.audience} · 利用 {c.redemption_count}
                {c.max_uses_total != null ? `/${c.max_uses_total}` : ''} ·{' '}
                {c.is_active ? '有効' : '無効'}
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
