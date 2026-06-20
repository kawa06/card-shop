'use client'

import { useState } from 'react'
import Link from 'next/link'
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

  // Phone verification
  const [phone, setPhone] = useState('')
  const [otpCode, setOtpCode] = useState('')
  const [isSendingOtp, setIsSendingOtp] = useState(false)
  const [isVerifyingOtp, setIsVerifyingOtp] = useState(false)
  const [isPhoneVerified, setIsPhoneVerified] = useState(false)
  const [showOtpField, setShowOtpField] = useState(false)

  const handleSendOtp = async () => {
    if (!phone.trim()) {
      setError('電話番号を入力してください')
      return
    }
    setIsSendingOtp(true)
    setError('')
    try {
      const res = await authApi.sendPhoneOtp(phone)
      toast({ 
        title: 'SMSを送信しました', 
        description: res.data.debug ? `Debug code: 000000` : '認証コードを入力してください' 
      })
      setShowOtpField(true)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'SMS送信に失敗しました')
    } finally {
      setIsSendingOtp(false)
    }
  }

  const handleVerifyOtp = async () => {
    if (!otpCode.trim() || otpCode.length !== 6) {
      setError('6桁の認証コードを入力してください')
      return
    }
    setIsVerifyingOtp(true)
    setError('')
    try {
      await authApi.verifyPhoneOtp(phone, otpCode)
      toast({ title: '認証に成功しました' })
      setIsPhoneVerified(true)
    } catch (err: any) {
      setError(err.response?.data?.detail || '認証に失敗しました')
    } finally {
      setIsVerifyingOtp(false)
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

    try {
      await register(email, password, name)
      toast({ 
        title: '会員登録が完了しました', 
        description: '認証メールを送信しました。メールをご確認ください。' 
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
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2 text-2xl font-bold">
            <span className="text-yellow-400">✦</span>
            <span className="text-white">KRX TCG</span>
          </Link>
          <p className="text-gray-400 mt-2 text-sm">新規会員登録</p>
        </div>

        <div className="bg-gray-900 rounded-xl border border-white/10 p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="name" className="text-gray-300">お名前</Label>
              <Input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="山田 太郎"
                required
                className="bg-gray-800 border-gray-700 text-white placeholder:text-gray-500 focus:border-yellow-400/50"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email" className="text-gray-300">メールアドレス</Label>
              <Input
                id="email"
                name="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="example@email.com"
                required
                autoComplete="email"
                className="bg-gray-800 border-gray-700 text-white placeholder:text-gray-500 focus:border-yellow-400/50"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-gray-300">パスワード</Label>
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
                className="bg-gray-800 border-gray-700 text-white placeholder:text-gray-500 focus:border-yellow-400/50"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirmPassword" className="text-gray-300">パスワード（確認）</Label>
              <Input
                id="confirmPassword"
                name="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete="new-password"
                className="bg-gray-800 border-gray-700 text-white placeholder:text-gray-500 focus:border-yellow-400/50"
              />
            </div>

            <div className="space-y-2 pt-2 border-t border-white/5">
              <Label htmlFor="phone" className="text-gray-300">電話番号認証</Label>
              <div className="flex gap-2">
                <Input
                  id="phone"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+819012345678"
                  disabled={isPhoneVerified}
                  className="bg-gray-800 border-gray-700 text-white placeholder:text-gray-500 focus:border-yellow-400/50"
                />
                <Button 
                  type="button" 
                  onClick={handleSendOtp} 
                  disabled={isSendingOtp || isPhoneVerified}
                  variant="outline"
                  className="border-yellow-400/50 text-yellow-400 hover:bg-yellow-400/10"
                >
                  {isSendingOtp ? '...' : isPhoneVerified ? '認証済' : 'SMS送信'}
                </Button>
              </div>
            </div>

            {showOtpField && !isPhoneVerified && (
              <div className="space-y-2 animate-in slide-in-from-top-1">
                <Label htmlFor="otp" className="text-gray-300">認証コード</Label>
                <div className="flex gap-2">
                  <Input
                    id="otp"
                    type="text"
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value)}
                    placeholder="000000"
                    maxLength={6}
                    className="bg-gray-800 border-gray-700 text-white placeholder:text-gray-500 focus:border-yellow-400/50"
                  />
                  <Button 
                    type="button" 
                    onClick={handleVerifyOtp} 
                    disabled={isVerifyingOtp}
                    className="bg-white text-gray-950 hover:bg-gray-200"
                  >
                    {isVerifyingOtp ? '...' : '認証する'}
                  </Button>
                </div>
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
