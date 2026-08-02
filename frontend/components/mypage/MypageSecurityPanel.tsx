'use client'

import { useEffect, useState } from 'react'
import { authApi } from '@/lib/api'
import { toast } from '@/lib/use-toast'
import { Button } from '@/components/ui/button'
import { Shield } from 'lucide-react'

type LoginHistoryItem = {
  id: number
  ip_address?: string | null
  method: string
  success: boolean
  created_at: string
}

export function MypageSecurityPanel() {
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(false)
  const [history, setHistory] = useState<LoginHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [toggling, setToggling] = useState(false)

  useEffect(() => {
    Promise.all([authApi.get2faSettings(), authApi.getLoginHistory()])
      .then(([settingsRes, historyRes]) => {
        setTwoFactorEnabled(Boolean(settingsRes.data.enabled))
        setHistory(historyRes.data)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const toggle2fa = async () => {
    setToggling(true)
    try {
      const next = !twoFactorEnabled
      await authApi.update2faSettings(next)
      setTwoFactorEnabled(next)
      toast({ title: next ? '2段階認証を有効にしました' : '2段階認証を無効にしました' })
    } catch {
      toast({ title: '設定の更新に失敗しました', variant: 'destructive' })
    } finally {
      setToggling(false)
    }
  }

  if (loading) return null

  return (
    <div className="mb-10 bg-gray-50 rounded-lg border border-gray-200 p-5">
      <h2 className="text-gray-900 font-semibold flex items-center gap-2 mb-4">
        <Shield className="h-4 w-4 text-gray-500" /> セキュリティ
      </h2>

      <div className="flex items-center justify-between gap-4 mb-6 pb-4 border-b border-gray-200">
        <div>
          <p className="text-sm font-medium text-gray-900">メールOTP 2段階認証</p>
          <p className="text-xs text-gray-500">ログイン時にメールで認証コードを送信します</p>
        </div>
        <Button variant={twoFactorEnabled ? 'default' : 'outline'} size="sm" disabled={toggling} onClick={toggle2fa}>
          {twoFactorEnabled ? '有効' : '無効'}
        </Button>
      </div>

      <p className="text-sm font-medium text-gray-900 mb-2">ログイン履歴（直近20件）</p>
      {history.length === 0 ? (
        <p className="text-xs text-gray-500">履歴がありません</p>
      ) : (
        <ul className="space-y-2 max-h-48 overflow-y-auto">
          {history.map((h) => (
            <li key={h.id} className="text-xs text-gray-600 flex justify-between gap-2">
              <span>
                {new Date(h.created_at).toLocaleString('ja-JP')} · {h.method}
                {h.ip_address ? ` · ${h.ip_address}` : ''}
              </span>
              <span className={h.success ? 'text-green-600' : 'text-red-600'}>
                {h.success ? '成功' : '失敗'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
