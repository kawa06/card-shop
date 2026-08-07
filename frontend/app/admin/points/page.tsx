'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { adminPointsApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

export default function AdminPointsPage() {
  const [settings, setSettings] = useState<any>(null)
  const [userId, setUserId] = useState('')
  const [userPoints, setUserPoints] = useState<any>(null)
  const [grantAmount, setGrantAmount] = useState('1000')
  const [grantReason, setGrantReason] = useState('')
  const [deductAmount, setDeductAmount] = useState('')
  const [deductReason, setDeductReason] = useState('')
  const [saving, setSaving] = useState(false)

  const loadSettings = async () => {
    const res = await adminPointsApi.getSettings()
    setSettings(res.data)
  }

  useEffect(() => {
    void loadSettings()
  }, [])

  const searchUser = async () => {
    const id = parseInt(userId, 10)
    if (!id) return
    const res = await adminPointsApi.getUser(id)
    setUserPoints(res.data)
  }

  const saveSettings = async () => {
    if (!settings) return
    setSaving(true)
    try {
      await adminPointsApi.updateSettings({
        enabled: settings.enabled,
        earn_rate_percent: Number(settings.earn_rate_percent),
        expiration_days: settings.expiration_days === '' ? null : Number(settings.expiration_days),
        max_points_per_order: Number(settings.max_points_per_order),
        max_usage_percent: Number(settings.max_usage_percent),
        points_apply_to_shipping: settings.points_apply_to_shipping,
      })
      toast({ title: '設定を保存しました' })
      await loadSettings()
    } catch (e: any) {
      toast({ title: 'エラー', description: e?.response?.data?.detail || '保存に失敗', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  const doGrant = async () => {
    const id = parseInt(userId, 10)
    const amount = parseInt(grantAmount, 10)
    if (!id || !amount || !grantReason.trim()) {
      toast({ title: '入力エラー', variant: 'destructive' })
      return
    }
    await adminPointsApi.grant({ user_id: id, amount, reason: grantReason.trim() })
    toast({ title: `${amount}pt を付与しました` })
    await searchUser()
  }

  const doDeduct = async () => {
    const id = parseInt(userId, 10)
    const amount = parseInt(deductAmount, 10)
    if (!id || !amount || !deductReason.trim()) {
      toast({ title: '入力エラー', variant: 'destructive' })
      return
    }
    if (!confirm(`${amount}pt を減算します。よろしいですか？`)) return
    await adminPointsApi.deduct({ user_id: id, amount, reason: deductReason.trim() })
    toast({ title: `${amount}pt を減算しました` })
    await searchUser()
  }

  return (
    <div className="container py-8 max-w-3xl">
      <div className="flex items-center gap-4 mb-6">
        <Link href="/admin" className="text-sm text-blue-600">← 管理画面</Link>
        <h1 className="text-2xl font-bold">ポイント管理</h1>
      </div>

      {settings && (
        <section className="border rounded-lg p-5 mb-8 space-y-4">
          <h2 className="font-semibold">ショップ設定</h2>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={!!settings.enabled}
              onChange={(e) => setSettings({ ...settings, enabled: e.target.checked })}
            />
            ポイント機能を有効化
          </label>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>付与率 (%)</Label>
              <Input
                type="number"
                value={settings.earn_rate_percent}
                onChange={(e) => setSettings({ ...settings, earn_rate_percent: e.target.value })}
              />
            </div>
            <div>
              <Label>有効期限 (日 / 空=無期限)</Label>
              <Input
                value={settings.expiration_days ?? ''}
                onChange={(e) => setSettings({ ...settings, expiration_days: e.target.value })}
              />
            </div>
            <div>
              <Label>1注文あたり上限 (pt)</Label>
              <Input
                type="number"
                value={settings.max_points_per_order}
                onChange={(e) => setSettings({ ...settings, max_points_per_order: e.target.value })}
              />
            </div>
            <div>
              <Label>利用率上限 (%)</Label>
              <Input
                type="number"
                value={settings.max_usage_percent}
                onChange={(e) => setSettings({ ...settings, max_usage_percent: e.target.value })}
              />
            </div>
          </div>
          <Button onClick={saveSettings} disabled={saving}>
            {saving ? '保存中...' : '設定を保存'}
          </Button>
        </section>
      )}

      <section className="border rounded-lg p-5 space-y-4">
        <h2 className="font-semibold">ユーザー操作</h2>
        <div className="flex gap-2">
          <Input placeholder="ユーザーID" value={userId} onChange={(e) => setUserId(e.target.value)} />
          <Button type="button" variant="outline" onClick={searchUser}>検索</Button>
        </div>
        {userPoints && (
          <div className="bg-gray-50 rounded p-4 text-sm space-y-1">
            <p>{userPoints.name} ({userPoints.email})</p>
            <p>残高: <strong>{userPoints.available_points.toLocaleString()}pt</strong></p>
            <p>生涯獲得: {userPoints.lifetime_earned}pt / 利用: {userPoints.lifetime_used}pt</p>
          </div>
        )}
        <div className="grid md:grid-cols-2 gap-6">
          <div className="space-y-2 border rounded p-4">
            <h3 className="font-medium text-sm">手動付与</h3>
            <Input type="number" placeholder="ポイント数" value={grantAmount} onChange={(e) => setGrantAmount(e.target.value)} />
            <Input placeholder="理由 (必須)" value={grantReason} onChange={(e) => setGrantReason(e.target.value)} />
            <Button type="button" onClick={doGrant}>付与する</Button>
          </div>
          <div className="space-y-2 border rounded p-4">
            <h3 className="font-medium text-sm">手動減算</h3>
            <Input type="number" placeholder="ポイント数" value={deductAmount} onChange={(e) => setDeductAmount(e.target.value)} />
            <Input placeholder="理由 (必須)" value={deductReason} onChange={(e) => setDeductReason(e.target.value)} />
            <Button type="button" variant="destructive" onClick={doDeduct}>減算する</Button>
          </div>
        </div>
      </section>
    </div>
  )
}
