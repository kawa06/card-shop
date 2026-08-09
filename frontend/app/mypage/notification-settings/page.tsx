'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { notificationsApi } from '@/lib/api'
import { useBackendAuth } from '@/hooks/useBackendAuth'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'

type Settings = {
  in_app_enabled: boolean
  email_enabled: boolean
  order_in_app: boolean
  order_email: boolean
  shipping_in_app: boolean
  shipping_email: boolean
  appraisal_in_app: boolean
  appraisal_email: boolean
  live_in_app: boolean
  live_email: boolean
  auction_in_app: boolean
  auction_email: boolean
  campaign_in_app: boolean
  campaign_email: boolean
}

const TOGGLES: Array<{ key: keyof Settings; label: string }> = [
  { key: 'in_app_enabled', label: 'アプリ内通知（全体）' },
  { key: 'email_enabled', label: 'メール通知（全体）' },
  { key: 'order_in_app', label: '注文・アプリ内' },
  { key: 'order_email', label: '注文・メール' },
  { key: 'shipping_in_app', label: '配送・アプリ内' },
  { key: 'shipping_email', label: '配送・メール' },
  { key: 'appraisal_in_app', label: '査定・アプリ内' },
  { key: 'appraisal_email', label: '査定・メール' },
  { key: 'live_in_app', label: 'ライブ・アプリ内' },
  { key: 'live_email', label: 'ライブ・メール' },
  { key: 'auction_in_app', label: 'オークション・アプリ内' },
  { key: 'auction_email', label: 'オークション・メール' },
  { key: 'campaign_in_app', label: 'キャンペーン・アプリ内' },
  { key: 'campaign_email', label: 'キャンペーン・メール' },
]

export default function NotificationSettingsPage() {
  const { isLoggedIn, isReady, requireAuth } = useBackendAuth()
  const [settings, setSettings] = useState<Settings | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!isReady || !isLoggedIn) return
    void (async () => {
      const token = await requireAuth()
      if (!token) return
      const res = await notificationsApi.getSettings()
      setSettings(res.data)
    })()
  }, [isReady, isLoggedIn, requireAuth])

  if (!isReady || !isLoggedIn) return null

  const save = async () => {
    if (!settings) return
    setSaving(true)
    try {
      const res = await notificationsApi.updateSettings(settings as unknown as Record<string, boolean>)
      setSettings(res.data)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="container py-8 max-w-2xl px-4">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold" data-testid="notification-settings-heading">
          通知設定
        </h1>
        <Link href="/mypage/notifications" className="text-sm text-blue-600">
          通知一覧へ
        </Link>
      </div>
      {!settings ? (
        <p className="text-gray-500">読み込み中...</p>
      ) : (
        <div className="space-y-3" data-testid="notification-settings-form">
          {TOGGLES.map((t) => (
            <label key={t.key} className="flex items-center justify-between border rounded-md p-3">
              <Label htmlFor={t.key}>{t.label}</Label>
              <input
                id={t.key}
                type="checkbox"
                checked={Boolean(settings[t.key])}
                onChange={(e) => setSettings({ ...settings, [t.key]: e.target.checked })}
                data-testid={`notif-setting-${t.key}`}
              />
            </label>
          ))}
          <Button type="button" onClick={() => void save()} disabled={saving} data-testid="notification-settings-save">
            保存
          </Button>
        </div>
      )}
    </div>
  )
}
