'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2, Save } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminEmailApi } from '@/lib/api'
import { toast } from '@/lib/use-toast'
import { Button } from '@/components/ui/button'

type AutoSendSettings = Record<string, boolean>
type ChannelSettings = Record<string, string>
type RecipientSettings = Record<string, { mode: string; permission_codes: string[]; custom_emails: string[] }>

type NotifyEvent = {
  event_key: string
  template_key: string
  label: string
  category: string
  channel_default: string
}

const CHANNEL_LABELS: Record<string, string> = {
  email: 'メールのみ',
  in_app: '管理画面のみ',
  both: '両方',
}

const MODE_LABELS: Record<string, string> = {
  all_admins: '全管理者',
  by_permission: '権限ごと',
  assignee_only: '担当者のみ',
  custom_emails: 'メール直接入力',
}

export default function AdminNotifySettingsPage() {
  const { isReady } = useAdminGuard()
  const [events, setEvents] = useState<NotifyEvent[]>([])
  const [autoSend, setAutoSend] = useState<AutoSendSettings>({})
  const [channels, setChannels] = useState<ChannelSettings>({})
  const [recipients, setRecipients] = useState<RecipientSettings>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [filter, setFilter] = useState('all')

  const categories = useMemo(() => {
    const set = new Set(events.map((e) => e.category))
    return ['all', ...Array.from(set)]
  }, [events])

  const filtered = useMemo(
    () => (filter === 'all' ? events : events.filter((e) => e.category === filter)),
    [events, filter]
  )

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [evRes, autoRes, chRes, recRes] = await Promise.all([
        adminEmailApi.getAdminNotifyEvents(),
        adminEmailApi.getAdminNotifyAutoSend(),
        adminEmailApi.getAdminNotifyChannels(),
        adminEmailApi.getAdminNotifyRecipients(),
      ])
      setEvents(evRes.data || [])
      setAutoSend(autoRes.data.settings || {})
      setChannels(chRes.data.settings || {})
      setRecipients(recRes.data.settings || {})
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
      const [autoRes, chRes, recRes] = await Promise.all([
        adminEmailApi.updateAdminNotifyAutoSend(autoSend),
        adminEmailApi.updateAdminNotifyChannels(channels),
        adminEmailApi.updateAdminNotifyRecipients(recipients),
      ])
      setAutoSend(autoRes.data.settings)
      setChannels(chRes.data.settings)
      setRecipients(recRes.data.settings)
      toast({ title: '管理者通知設定を保存しました' })
    } catch {
      toast({ title: '保存に失敗しました', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  if (!isReady || loading) {
    return (
      <div className="container py-12 flex justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/admin/settings/email" className="text-gray-500 hover:text-gray-900">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <h1 className="text-2xl font-bold">管理者通知設定</h1>
      </div>

      <p className="text-sm text-gray-600 mb-4">
        イベントごとにメール通知・管理画面通知・通知先を設定します。テンプレート本文はメール設定から編集できます。
      </p>

      <div className="flex flex-wrap gap-2 mb-6">
        {categories.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => setFilter(c)}
            className={`px-3 py-1 rounded-full text-sm border ${
              filter === c ? 'bg-yellow-400 border-yellow-400 text-gray-950 font-medium' : 'bg-white border-gray-200 text-gray-600'
            }`}
          >
            {c === 'all' ? 'すべて' : c}
          </button>
        ))}
      </div>

      <div className="space-y-4 mb-8">
        {filtered.map((ev) => {
          const rec = recipients[ev.event_key] || recipients._default || { mode: 'all_admins', permission_codes: [], custom_emails: [] }
          return (
            <div key={ev.event_key} className="rounded-lg border border-gray-200 bg-white p-4 space-y-3">
              <div className="flex flex-wrap justify-between gap-2">
                <div>
                  <p className="font-medium text-gray-900">{ev.label}</p>
                  <p className="text-xs text-gray-500 font-mono">{ev.event_key}</p>
                </div>
                <Link
                  href={`/admin/settings/email/${encodeURIComponent(ev.template_key)}`}
                  className="text-xs text-yellow-700 hover:underline"
                >
                  テンプレート編集
                </Link>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={autoSend[ev.event_key] ?? true}
                    onChange={(e) => setAutoSend((p) => ({ ...p, [ev.event_key]: e.target.checked }))}
                  />
                  メール自動送信
                </label>
                <div>
                  <label className="text-xs text-gray-500 block mb-1">通知チャネル</label>
                  <select
                    className="w-full rounded border border-gray-200 px-2 py-1 text-sm"
                    value={channels[ev.event_key] || ev.channel_default}
                    onChange={(e) => setChannels((p) => ({ ...p, [ev.event_key]: e.target.value }))}
                  >
                    {Object.entries(CHANNEL_LABELS).map(([k, label]) => (
                      <option key={k} value={k}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-gray-500 block mb-1">通知先</label>
                  <select
                    className="w-full rounded border border-gray-200 px-2 py-1 text-sm"
                    value={rec.mode || 'all_admins'}
                    onChange={(e) =>
                      setRecipients((p) => ({
                        ...p,
                        [ev.event_key]: { ...rec, mode: e.target.value },
                      }))
                    }
                  >
                    {Object.entries(MODE_LABELS).map(([k, label]) => (
                      <option key={k} value={k}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              {rec.mode === 'custom_emails' && (
                <input
                  className="w-full rounded border border-gray-200 px-2 py-1 text-sm"
                  placeholder="email1@example.com, email2@example.com"
                  value={(rec.custom_emails || []).join(', ')}
                  onChange={(e) =>
                    setRecipients((p) => ({
                      ...p,
                      [ev.event_key]: {
                        ...rec,
                        custom_emails: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                      },
                    }))
                  }
                />
              )}
              {rec.mode === 'by_permission' && (
                <input
                  className="w-full rounded border border-gray-200 px-2 py-1 text-sm"
                  placeholder="admin.orders.read, admin.buyback.read"
                  value={(rec.permission_codes || []).join(', ')}
                  onChange={(e) =>
                    setRecipients((p) => ({
                      ...p,
                      [ev.event_key]: {
                        ...rec,
                        permission_codes: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                      },
                    }))
                  }
                />
              )}
            </div>
          )
        })}
      </div>

      <Button onClick={() => void handleSave()} disabled={saving}>
        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
        保存
      </Button>
    </div>
  )
}
