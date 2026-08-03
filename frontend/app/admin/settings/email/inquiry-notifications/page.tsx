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
  inquiry_received: 'お問い合わせ受付完了',
  inquiry_admin_reply: '管理者から返信',
  inquiry_info_request: '追加情報のお願い',
  inquiry_attachment_received: '添付ファイル受領',
  inquiry_in_progress: '対応中',
  inquiry_on_hold: '対応保留',
  inquiry_resolved: '対応完了',
  inquiry_closed: 'お問い合わせ終了',
  inquiry_reopened: 'お問い合わせ再開',
  inquiry_cancelled: 'お問い合わせキャンセル',
  inquiry_system_error: 'システムエラー',
}

export default function InquiryEmailNotificationsPage() {
  const { isReady } = useAdminGuard()
  const [settings, setSettings] = useState<AutoSendSettings>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await adminEmailApi.getInquiryAutoSend()
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
      const res = await adminEmailApi.updateInquiryAutoSend(settings)
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
      <div className="container py-12 flex justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/admin/settings/email" className="text-gray-500 hover:text-gray-900">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <h1 className="text-2xl font-bold">お問い合わせメール — 自動送信設定</h1>
      </div>

      <p className="text-sm text-gray-600 mb-6">
        各イベントの自動送信 ON/OFF を設定します。管理画面から個別に「送信しない」を選ぶこともできます。
      </p>

      <div className="space-y-3 mb-8">
        {Object.entries(settings).map(([key, enabled]) => (
          <label key={key} className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4">
            <span className="text-sm font-medium text-gray-900">{EVENT_LABELS[key] || key}</span>
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setSettings((prev) => ({ ...prev, [key]: e.target.checked }))}
              className="h-4 w-4"
            />
          </label>
        ))}
      </div>

      <Button onClick={() => void handleSave()} disabled={saving}>
        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
        保存
      </Button>
    </div>
  )
}
