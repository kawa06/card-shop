'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2, Save } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminInquiriesApi } from '@/lib/api'
import { InquirySettings } from '@/lib/types'
import { toast } from '@/lib/use-toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function AdminInquirySettingsPage() {
  const { isReady } = useAdminGuard()
  const [settings, setSettings] = useState<InquirySettings | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const load = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await adminInquiriesApi.getSettings()
      setSettings(res.data)
    } catch {
      toast({ title: '設定の取得に失敗しました', variant: 'destructive' })
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void load()
  }, [isMounted, isReady, load])

  const update = (patch: Partial<InquirySettings>) => {
    if (!settings) return
    setSettings({ ...settings, ...patch })
  }

  const handleSave = async () => {
    if (!settings) return
    setIsSaving(true)
    try {
      const res = await adminInquiriesApi.updateSettings(settings)
      setSettings(res.data)
      toast({ title: '問い合わせ設定を保存しました' })
    } catch {
      toast({ title: '保存に失敗しました', variant: 'destructive' })
    } finally {
      setIsSaving(false)
    }
  }

  if (!isMounted || !isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-2xl">
        <Link href="/admin/inquiries" className="inline-flex items-center gap-2 text-gray-500 hover:text-gray-900 text-sm mb-6">
          <ArrowLeft className="h-4 w-4" />
          問い合わせ管理
        </Link>

        <h1 className="text-2xl font-bold text-gray-900 mb-6">問い合わせ設定</h1>

        {isLoading || !settings ? (
          <div className="h-40 bg-gray-50 rounded animate-pulse" />
        ) : (
          <div className="space-y-5 border border-gray-200 rounded-lg p-6 bg-gray-50">
            <Toggle
              label="問い合わせ機能を有効にする"
              checked={settings.enabled}
              onChange={(v) => update({ enabled: v })}
            />
            <Toggle
              label="添付ファイルを許可"
              checked={settings.attachments_enabled}
              onChange={(v) => update({ attachments_enabled: v })}
            />
            <Toggle
              label="自動返信メール"
              checked={settings.auto_reply_enabled}
              onChange={(v) => update({ auto_reply_enabled: v })}
            />
            <Toggle
              label="解決済み問い合わせの再開を許可"
              checked={settings.allow_reopen_resolved}
              onChange={(v) => update({ allow_reopen_resolved: v })}
            />

            <div>
              <Label>自動クローズ（日数）</Label>
              <Input
                type="number"
                className="mt-1 w-32"
                value={settings.auto_close_days}
                onChange={(e) => update({ auto_close_days: parseInt(e.target.value, 10) || 30 })}
              />
            </div>

            <div>
              <Label>最大添付数</Label>
              <Input
                type="number"
                className="mt-1 w-32"
                value={settings.max_attachments}
                onChange={(e) => update({ max_attachments: parseInt(e.target.value, 10) || 5 })}
              />
            </div>

            <div>
              <Label>最大添付サイズ（バイト）</Label>
              <Input
                type="number"
                className="mt-1 w-40"
                value={settings.max_attachment_bytes}
                onChange={(e) => update({ max_attachment_bytes: parseInt(e.target.value, 10) || 5242880 })}
              />
            </div>

            <Button onClick={() => void handleSave()} disabled={isSaving}>
              {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
              保存
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <label className="flex items-center gap-3 text-sm">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  )
}
