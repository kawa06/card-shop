'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuthStore } from '@/store/auth'

export function TwoFactorGate() {
  const pending2fa = useAuthStore((s) => s.pending2fa)
  const verify2fa = useAuthStore((s) => s.verify2fa)
  const clearPending2fa = useAuthStore((s) => s.clearPending2fa)
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (!pending2fa) return null

  const handleVerify = async () => {
    setLoading(true)
    setError('')
    try {
      await verify2fa(code)
      setCode('')
    } catch (e) {
      setError(e instanceof Error ? e.message : '認証に失敗しました')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[100] bg-black/50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl p-6 max-w-sm w-full shadow-xl">
        <h2 className="text-lg font-bold text-gray-900 mb-2">2段階認証</h2>
        <p className="text-sm text-gray-600 mb-4">
          メールに送信された6桁の認証コードを入力してください。
        </p>
        <Input
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          placeholder="000000"
          className="mb-3 text-center tracking-widest"
          inputMode="numeric"
        />
        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
        <div className="flex gap-2">
          <Button variant="outline" className="flex-1" onClick={clearPending2fa}>
            キャンセル
          </Button>
          <Button className="flex-1" disabled={loading || code.length < 6} onClick={handleVerify}>
            {loading ? '確認中…' : '認証'}
          </Button>
        </div>
      </div>
    </div>
  )
}
