'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

export default function LoginPage() {
  const router = useRouter()
  const { login, isLoading } = useAuthStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await login(email, password)
      toast({ title: 'ログインしました' })
      router.push('/')
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'ログインに失敗しました'
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
            <span className="text-white">Oripa_kawa</span>
          </Link>
          <p className="text-gray-400 mt-2 text-sm">アカウントにログイン</p>
        </div>

        <div className="bg-gray-900 rounded-xl border border-white/10 p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-gray-300">メールアドレス</Label>
              <Input
                id="email"
                name="username"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="example@email.com"
                required
                autoComplete="username"
                className="bg-gray-800 border-gray-700 text-white placeholder:text-gray-500 focus:border-yellow-400/50"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-gray-300">パスワード</Label>
              <Input
                id="password"
                name="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete="current-password"
                className="bg-gray-800 border-gray-700 text-white placeholder:text-gray-500 focus:border-yellow-400/50"
              />
            </div>

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
              {isLoading ? 'ログイン中...' : 'ログイン'}
            </Button>
          </form>

          <div className="mt-6 text-center text-sm">
            <span className="text-gray-500">アカウントをお持ちでない方は</span>{' '}
            <Link href="/register" className="text-yellow-400 hover:text-yellow-300 font-medium">
              会員登録
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
