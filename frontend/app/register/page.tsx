'use client'

import { useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/auth'
import { authApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

export default function RegisterPage() {
  const router = useRouter()
  const { register, isLoading } = useAuthStore()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')

  const [phone, setPhone] = useState('')
  const [otpCode, setOtpCode] = useState('')
  const [isSendingOtp, setIsSendingOtp] = useState(false)
  const [showOtpField, setShowOtpField] = useState(false)
  const [isDebugMode, setIsDebugMode] = useState(false)

  const normalizePhone = (raw: string) => {
    const cleaned = raw.trim().replace(/[\s-]/g, '')
    if (cleaned.startsWith('0') && cleaned.length > 0) {
      return '+81' + cleaned.slice(1)
    }
    return cleaned
  }

  const handleSendOtp = async () => {
    if (!phone.trim()) {
      setError('電話番号を入力してください')
      return
    }
    setIsSendingOtp(true)
    setError('')
    try {
      const normalizedPhone = normalizePhone(phone)
      const res = await authApi.sendPhoneOtp(normalizedPhone)
      setPhone(normalizedPhone)
      setIsDebugMode(res.data.debug || false)
      toast({
        title: '送信しました',
        description: res.data.debug
          ? 'SMSをご確認ください（デモ環境: 認証コードは 000000）'
          : 'SMSをご確認ください / SMS sent, please check your phone',
      })
      setShowOtpField(true)
      setOtpCode('')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'SMS送信に失敗しました')
    } finally {
      setIsSendingOtp(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (password !== confirmPassword) {
      setError('パスワードが一致しません')
      return
    }
    if (password.length < 8) {
      setError('パスワードは8文字以上で入力してください')
      return
    }

    const wantsPhoneVerify = showOtpField && phone.trim()
    if (wantsPhoneVerify && otpCode.length !== 6) {
      setError('6桁の認証コードを入力してください')
      return
    }

    try {
      await register(
        email,
        password,
        name,
        wantsPhoneVerify ? { number: phone, code: otpCode } : undefined
      )
      toast({
        title: '会員登録が完了しました',
        description: '認証メールを送信しました。メールをご確認ください。',
      })
      router.push('/mypage')
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        '会員登録に失敗しました'
      setError(message)
    }
  }

  return (
    <div className="min-h-screen bg-white flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2 text-2xl font-bold">
            <div className="relative h-10 w-10 flex-shrink-0 overflow-hidden rounded-md border border-yellow-400/20">
              <Image
                src="/logo-main.png"
                alt="KRX TCG"
                fill
                className="object-contain"
                priority
              />
            </div>
            <span className="text-gray-900">KRX TCG</span>
          </Link>
          <p className="text-gray-400 mt-2 text-sm">新規会員登録</p>
        </div>

        <div className="bg-gray-50 rounded-xl border border-gray-200 p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="name" className="text-gray-600">お名前</Label>
              <Input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="山田 太郎"
                required
                className="bg-white border-gray-300 text-gray-900 placeholder:text-gray-400 focus:border-yellow-400/50"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email" className="text-gray-600">メールアドレス</Label>
              <Input
                id="email"
                name="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="example@email.com"
                required
                autoComplete="email"
                className="bg-white border-gray-300 text-gray-900 placeholder:text-gray-400 focus:border-yellow-400/50"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-gray-600">パスワード</Label>
              <Input
                id="password"
                name="new-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="8文字以上"
                required
                minLength={8}
                autoComplete="new-password"
                className="bg-white border-gray-300 text-gray-900 placeholder:text-gray-400 focus:border-yellow-400/50"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirmPassword" className="text-gray-600">パスワード（確認）</Label>
              <Input
                id="confirmPassword"
                name="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete="new-password"
                className="bg-white border-gray-300 text-gray-900 placeholder:text-gray-400 focus:border-yellow-400/50"
              />
            </div>

            <div className="space-y-2 pt-2 border-t border-gray-100">
              <Label htmlFor="phone" className="text-gray-600">電話番号 / Phone number（任意）</Label>
              <div className="flex gap-2">
                <Input
                  id="phone"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="例: 09012345678 / e.g. 09012345678"
                  className="bg-white border-gray-300 text-gray-900 placeholder:text-gray-400 focus:border-yellow-400/50"
                />
                <Button
                  type="button"
                  onClick={handleSendOtp}
                  disabled={isSendingOtp || !phone.trim()}
                  variant="outline"
                  className="border-yellow-400/50 text-yellow-400 hover:bg-yellow-400/10 whitespace-nowrap"
                >
                  {isSendingOtp ? '...' : 'SMS送信'}
                </Button>
              </div>
              <p className="text-gray-500 text-xs">国際形式（+81...）でも入力可 / International format also accepted</p>
            </div>

            {showOtpField && (
              <div className="space-y-2 animate-in slide-in-from-top-1">
                <Label htmlFor="otp" className="text-gray-600">認証コード / Verification Code</Label>
                <Input
                  id="otp"
                  type="text"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  placeholder="6桁のコード / 6-digit code"
                  maxLength={6}
                  className="bg-white border-gray-300 text-gray-900 placeholder:text-gray-400 focus:border-yellow-400/50"
                />
                <p className="text-gray-500 text-xs">会員登録時に電話番号を認証します / Phone is verified when you register</p>
                {isDebugMode && (
                  <p className="text-gray-500 text-xs">デモ環境: 認証コードは 000000 / Demo: use code 000000</p>
                )}
              </div>
            )}

            {error && (
              <p className="text-red-400 text-sm bg-red-400/10 px-3 py-2 rounded border border-red-400/20">
                {error}
              </p>
            )}

            <Button
              type="submit"
              disabled={isLoading}
              className="w-full h-11 bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold"
            >
              {isLoading ? '登録中...' : '会員登録'}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm">
            <span className="text-gray-500">すでにアカウントをお持ちの方は</span>{' '}
            <Link href="/login" className="text-yellow-400 hover:text-yellow-300 font-medium">
              ログイン
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
