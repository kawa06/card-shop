'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { CheckCircle2, XCircle, Loader2, ArrowRight } from 'lucide-react'
import { authApi } from '@/lib/api'
import { Button } from '@/components/ui/button'
import Link from 'next/link'

export default function VerifyPage({ params }: { params: { token: string } }) {
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')
  const router = useRouter()

  useEffect(() => {
    const verify = async () => {
      try {
        const res = await authApi.verifyEmail(params.token)
        setStatus('success')
        setMessage(res.data.message)
      } catch (err: any) {
        setStatus('error')
        setMessage(err.response?.data?.detail || '認証に失敗しました。トークンが無効か期限切れです。')
      }
    }
    verify()
  }, [params.token])

  return (
    <div className="min-h-[80vh] flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-gray-900 rounded-2xl border border-white/10 p-8 text-center shadow-2xl">
        {status === 'loading' && (
          <div className="space-y-4">
            <Loader2 className="h-12 w-12 text-yellow-400 animate-spin mx-auto" />
            <h1 className="text-xl font-bold text-white">メールアドレスを認証中...</h1>
            <p className="text-gray-400 text-sm">少々お待ちください</p>
          </div>
        )}

        {status === 'success' && (
          <div className="space-y-6">
            <div className="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mx-auto">
              <CheckCircle2 className="h-10 w-10 text-green-500" />
            </div>
            <div className="space-y-2">
              <h1 className="text-2xl font-bold text-white">認証が完了しました！</h1>
              <p className="text-gray-400 text-sm">{message}</p>
            </div>
            <Link href="/login">
              <Button className="w-full bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold h-11">
                ログインして始める
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </Link>
          </div>
        )}

        {status === 'error' && (
          <div className="space-y-6">
            <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto">
              <XCircle className="h-10 w-10 text-red-500" />
            </div>
            <div className="space-y-2">
              <h1 className="text-2xl font-bold text-white">認証エラー</h1>
              <p className="text-red-400/80 text-sm">{message}</p>
            </div>
            <div className="pt-4 flex flex-col gap-3">
              <Link href="/mypage">
                <Button variant="outline" className="w-full border-white/10 text-gray-300">
                  マイページへ
                </Button>
              </Link>
              <Link href="/">
                <Button variant="ghost" className="w-full text-gray-500">
                  トップに戻る
                </Button>
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
