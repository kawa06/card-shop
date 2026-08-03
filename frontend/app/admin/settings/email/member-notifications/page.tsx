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
  member_register_completed: '会員登録完了',
  member_email_verify: 'メールアドレス認証',
  member_email_verify_completed: 'メールアドレス認証完了',
  member_email_change_received: 'メールアドレス変更受付',
  member_email_change_completed: 'メールアドレス変更完了',
  member_phone_verify: '電話番号認証',
  member_phone_verify_completed: '電話番号認証完了',
  member_profile_updated: 'プロフィール変更完了',
  member_withdrawal_received: '退会受付',
  member_withdrawal_completed: '退会完了',
  login_success: 'ログイン成功通知',
  login_new_device: '新しい端末からのログイン',
  login_failed: 'ログイン失敗通知',
  login_failed_repeated: '連続ログイン失敗',
  login_account_locked: 'アカウントロック',
  login_account_unlocked: 'アカウントロック解除',
  password_reset_received: 'パスワード再設定受付',
  password_reset_completed: 'パスワード再設定完了',
  password_changed: 'パスワード変更完了',
  security_important_notice: '重要なお知らせ',
  security_suspicious_access: '不審なアクセス検知',
  security_settings_changed: 'セキュリティ設定変更',
  security_2fa_enabled: '二段階認証有効',
  security_2fa_disabled: '二段階認証無効',
  security_2fa_otp_sent: '二段階認証コード送信',
  security_terms_updated: '利用規約改定',
  security_privacy_updated: 'プライバシーポリシー改定',
  security_system_error: 'システムエラー',
}

export default function MemberEmailNotificationsPage() {
  const { isReady } = useAdminGuard()
  const [settings, setSettings] = useState<AutoSendSettings>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await adminEmailApi.getMemberAutoSend()
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
      const res = await adminEmailApi.updateMemberAutoSend(settings)
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
      <h1 className="text-2xl font-bold mb-2">会員・ログイン・セキュリティメール — 自動送信設定</h1>
      <p className="text-sm text-gray-500 mb-6">
        イベントごとに自動送信のON/OFFを設定できます。パスワード・認証コード等の機密情報はメール本文に含めない設計です。
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
