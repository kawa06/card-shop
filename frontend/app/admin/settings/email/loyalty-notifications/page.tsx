'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2, Save } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminEmailApi } from '@/lib/api'
import { toast } from '@/lib/use-toast'
import { Button } from '@/components/ui/button'

type AutoSendSettings = Record<string, boolean>

const EVENT_LABELS: Record<string, string> = {
  point_granted: 'ポイント付与',
  point_used: 'ポイント利用完了',
  point_scheduled: 'ポイント付与予定',
  point_expiry_notice: 'ポイント有効期限のお知らせ',
  point_expiry_scheduled: 'ポイント失効予定',
  point_expired: 'ポイント失効完了',
  point_adjusted: 'ポイント調整',
  coupon_distributed: 'クーポン配布',
  coupon_limited: '限定クーポン配布',
  coupon_birthday: '誕生日クーポン',
  coupon_used: 'クーポン利用完了',
  coupon_expiry_notice: 'クーポン利用期限のお知らせ',
  coupon_expiry_soon: 'クーポン期限間近',
  coupon_expired: 'クーポン期限切れ',
  coupon_cancelled: 'クーポン取消',
  rank_up: 'ランクアップ',
  rank_down: 'ランクダウン',
  rank_maintained: 'ランク維持',
  rank_update_notice: 'ランク更新のお知らせ',
  rank_next_notice: '次ランクまでのお知らせ',
  rank_benefit_granted: 'ランク特典付与',
  campaign_point_up: 'ポイントアップキャンペーン',
  campaign_rank_up: 'ランクアップキャンペーン',
  campaign_limited_event: '期間限定イベント',
  loyalty_system_error: 'システムエラー',
}

export default function LoyaltyEmailNotificationsPage() {
  const { isReady } = useAdminGuard()
  const [settings, setSettings] = useState<AutoSendSettings>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await adminEmailApi.getLoyaltyAutoSend()
      setSettings(res.data.settings || {})
    } catch {
      toast({ title: '設定の取得に失敗しました', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isReady) void load()
  }, [isReady, load])

  const handleSave = async () => {
    setSaving(true)
    try {
      const res = await adminEmailApi.updateLoyaltyAutoSend(settings)
      setSettings(res.data.settings)
      toast({ title: '自動送信設定を保存しました' })
    } catch {
      toast({ title: '保存に失敗しました', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  if (!isReady || loading) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  const entries = Object.entries(settings).sort(([a], [b]) => a.localeCompare(b))

  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl">
      <Link href="/admin/settings/email" className="inline-flex items-center gap-2 text-gray-500 mb-4">
        <ArrowLeft className="h-4 w-4" /> メールテンプレート管理
      </Link>
      <h1 className="text-2xl font-bold mb-2">ポイント・クーポン・会員ランクメール — 自動送信設定</h1>
      <p className="text-sm text-gray-500 mb-6">
        イベントごとに自動送信のON/OFFを設定できます。ポイント・ランクの計算はメール送信と分離され、表示用スナップショットのみ渡されます。
      </p>

      <div className="space-y-2 bg-white border rounded-xl p-4">
        {entries.map(([key, enabled]) => (
          <label key={key} className="flex items-center justify-between gap-4 py-2 border-b last:border-0">
            <span className="text-sm text-gray-700">
              <span className="font-medium">{EVENT_LABELS[key] || key}</span>
              <span className="block font-mono text-xs text-gray-400">{key}</span>
            </span>
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setSettings({ ...settings, [key]: e.target.checked })}
              className="h-4 w-4"
            />
          </label>
        ))}
      </div>

      <Button onClick={handleSave} disabled={saving} className="mt-6">
        <Save className="h-4 w-4 mr-1" />
        {saving ? '保存中…' : '保存'}
      </Button>
    </div>
  )
}
