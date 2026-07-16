'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

export default function LoginPage() {
  const router = useRouter()
  const { login, isLoading, hasHydrated, setHasHydrated } = useAuthStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (hasHydrated) return
    const init = async () => {
      await useAuthStore.persist.rehydrate()
      setHasHydrated(true)
    }
    init()
  }, [hasHydrated, setHasHydrated])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await login(email, password)
      toast({ title: 'ログインしました' })
      router.push('/')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string | { msg: string }[] } } })?.response?.data?.detail
      const message = typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg).join(', ')
          : 'ログインに失敗しました'
      setError(message)
    }
  }

  return (
    <div className="min-h-[70vh] bg-white flex items-center justify-center p-4">
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
          <p className="text-gray-500 mt-2 text-sm">アカウントにログイン</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-gray-700">メールアドレス</Label>
              <Input
                id="email"
                name="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="example@email.com"
                required
                autoComplete="email"
                className="bg-white border-gray-300 text-gray-900 placeholder:text-gray-400 focus:border-yellow-400"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-gray-700">パスワード</Label>
              <Input
                id="password"
                name="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete="current-password"
                className="bg-white border-gray-300 text-gray-900 placeholder:text-gray-400 focus:border-yellow-400"
              />
            </div>

            {error && (
              <p className="text-red-600 text-sm bg-red-50 px-3 py-2 rounded border border-red-200">
                {error}
              </p>
            )}

            <Button
              type="submit"
              disabled={isLoading}
              className="w-full h-11 bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold"
            >
              {isLoading ? 'ログイン中...' : 'ログイン'}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm">
            <span className="text-gray-500">アカウントをお持ちでない方は</span>{' '}
            <Link href="/register" className="text-yellow-600 hover:text-yellow-500 font-medium">
              会員登録
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
