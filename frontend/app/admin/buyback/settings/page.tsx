'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2, Save } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminBuybackApi } from '@/lib/api'
import type { BuybackBusinessDayHours, BuybackChannelSettings } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

const WEEKDAYS: { key: string; label: string }[] = [
  { key: 'mon', label: '月' },
  { key: 'tue', label: '火' },
  { key: 'wed', label: '水' },
  { key: 'thu', label: '木' },
  { key: 'fri', label: '金' },
  { key: 'sat', label: '土' },
  { key: 'sun', label: '日' },
]

const defaultDay = (): BuybackBusinessDayHours => ({ open: '10:00', close: '19:00', closed: false })

export default function AdminBuybackSettingsPage() {
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const canWrite = hasPermission('buyback.settings.write')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [settings, setSettings] = useState<BuybackChannelSettings | null>(null)
  const [closedDatesText, setClosedDatesText] = useState('')

  const load = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await adminBuybackApi.getChannelSettings()
      setSettings(res.data)
      setClosedDatesText((res.data.closed_dates || []).join('\n'))
    } catch {
      toast({ title: '設定の取得に失敗しました', variant: 'destructive' })
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isReady) void load()
  }, [isReady, load])

  const updateDay = (key: string, patch: Partial<BuybackBusinessDayHours>) => {
    if (!settings) return
    setSettings({
      ...settings,
      business_hours: {
        ...settings.business_hours,
        [key]: { ...(settings.business_hours[key] || defaultDay()), ...patch },
      },
    })
  }

  const handleSave = async () => {
    if (!settings || !canWrite) return
    setIsSaving(true)
    try {
      const closed_dates = closedDatesText
        .split(/\r?\n/)
        .map((s) => s.trim())
        .filter(Boolean)
      const res = await adminBuybackApi.updateChannelSettings({
        store_enabled: settings.store_enabled,
        mail_enabled: settings.mail_enabled,
        slot_interval_minutes: settings.slot_interval_minutes,
        business_hours: settings.business_hours,
        closed_dates,
      })
      setSettings(res.data)
      setClosedDatesText((res.data.closed_dates || []).join('\n'))
      toast({ title: '買取チャネル設定を保存しました' })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast({
        title: '保存に失敗しました',
        description: typeof detail === 'string' ? detail : undefined,
        variant: 'destructive',
      })
    } finally {
      setIsSaving(false)
    }
  }

  if (!isReady || isLoading || !settings) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8 p-4 md:p-8">
      <div className="flex items-center gap-3">
        <Link href="/admin" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold">買取チャネル設定</h1>
          <p className="text-sm text-muted-foreground">店舗買取・郵送買取・営業時間・予約枠</p>
        </div>
      </div>

      <section className="space-y-4 rounded-xl border bg-card p-6">
        <h2 className="font-semibold">買取方法</h2>
        <label className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={settings.store_enabled}
            disabled={!canWrite}
            onChange={(e) => setSettings({ ...settings, store_enabled: e.target.checked })}
          />
          店舗買取を受け付ける
        </label>
        <label className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={settings.mail_enabled}
            disabled={!canWrite}
            onChange={(e) => setSettings({ ...settings, mail_enabled: e.target.checked })}
          />
          郵送買取を受け付ける
        </label>
        <p className="text-sm text-muted-foreground">
          現在のモード: <strong>{settings.channel_mode}</strong>（{settings.allowed_methods.join(' / ') || 'なし'}）
        </p>
      </section>

      <section className="space-y-4 rounded-xl border bg-card p-6">
        <h2 className="font-semibold">予約枠</h2>
        <div className="max-w-xs space-y-2">
          <Label htmlFor="slotInterval">予約可能時間の間隔（分）</Label>
          <select
            id="slotInterval"
            className="w-full rounded-md border bg-background px-3 py-2"
            value={settings.slot_interval_minutes}
            disabled={!canWrite}
            onChange={(e) =>
              setSettings({ ...settings, slot_interval_minutes: Number(e.target.value) })
            }
          >
            <option value={15}>15分</option>
            <option value={30}>30分</option>
            <option value={60}>60分</option>
          </select>
        </div>
      </section>

      <section className="space-y-4 rounded-xl border bg-card p-6">
        <h2 className="font-semibold">営業時間</h2>
        <div className="space-y-3">
          {WEEKDAYS.map(({ key, label }) => {
            const day = settings.business_hours[key] || defaultDay()
            return (
              <div key={key} className="grid gap-2 rounded-lg border p-3 md:grid-cols-[3rem_1fr_1fr_auto] md:items-center">
                <span className="font-medium">{label}</span>
                <Input
                  type="time"
                  value={day.open}
                  disabled={!canWrite || day.closed}
                  onChange={(e) => updateDay(key, { open: e.target.value })}
                />
                <Input
                  type="time"
                  value={day.close}
                  disabled={!canWrite || day.closed}
                  onChange={(e) => updateDay(key, { close: e.target.value })}
                />
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={day.closed}
                    disabled={!canWrite}
                    onChange={(e) => updateDay(key, { closed: e.target.checked })}
                  />
                  定休
                </label>
              </div>
            )
          })}
        </div>
      </section>

      <section className="space-y-4 rounded-xl border bg-card p-6">
        <h2 className="font-semibold">臨時定休日</h2>
        <p className="text-sm text-muted-foreground">1行に1日（YYYY-MM-DD）</p>
        <textarea
          className="min-h-[120px] w-full rounded-md border bg-background px-3 py-2 font-mono text-sm"
          value={closedDatesText}
          disabled={!canWrite}
          onChange={(e) => setClosedDatesText(e.target.value)}
          placeholder={'2026-08-15\n2026-12-31'}
        />
      </section>

      {canWrite && (
        <Button onClick={() => void handleSave()} disabled={isSaving}>
          {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          保存
        </Button>
      )}
    </div>
  )
}
