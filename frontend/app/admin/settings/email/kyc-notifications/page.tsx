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
  kyc_identity_received: '本人確認受付',
  kyc_identity_upload_completed: '本人確認書類アップロード完了',
  kyc_identity_review_started: '本人確認審査開始',
  kyc_identity_approved: '本人確認承認',
  kyc_identity_returned: '本人確認差し戻し',
  kyc_identity_resubmit_requested: '本人確認再提出依頼',
  kyc_identity_rejected: '本人確認却下',
  kyc_identity_expiry_notice: '本人確認有効期限のお知らせ',
  kyc_guardian_consent_requested: '保護者同意依頼',
  kyc_guardian_consent_received: '保護者同意受付',
  kyc_guardian_consent_completed: '保護者同意完了',
  kyc_guardian_identity_received: '保護者本人確認受付',
  kyc_guardian_identity_upload_completed: '保護者本人確認書類アップロード完了',
  kyc_guardian_identity_review_started: '保護者本人確認審査開始',
  kyc_guardian_identity_approved: '保護者本人確認承認',
  kyc_guardian_identity_returned: '保護者本人確認差し戻し',
  kyc_guardian_identity_resubmit_requested: '保護者本人確認再提出依頼',
  kyc_guardian_identity_rejected: '保護者本人確認却下',
  kyc_guardian_consent_expiry_notice: '保護者同意期限のお知らせ',
  kyc_auth_info_changed: '認証情報変更',
  kyc_auth_revoked: '認証取消',
  kyc_system_error: 'システムエラー',
}

export default function KycEmailNotificationsPage() {
  const { isReady } = useAdminGuard()
  const [settings, setSettings] = useState<AutoSendSettings>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await adminEmailApi.getKycAutoSend()
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
      const res = await adminEmailApi.updateKycAutoSend(settings)
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
      <h1 className="text-2xl font-bold mb-2">本人確認・保護者同意メール — 自動送信設定</h1>
      <p className="text-sm text-gray-500 mb-6">
        ステータス変更時にメールを自動送信するかをイベントごとに設定できます。OFFにしても管理画面から手動再送できます。
        個人情報・書類URLはメール本文に含めない設計です。
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
