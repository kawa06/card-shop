'use client'

import Link from 'next/link'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { ShoppingCart, Search, User, LogOut, Shield, Menu, X, Globe, Mail, Smartphone } from 'lucide-react'
import { useState, useEffect } from 'react'
import { useAuthStore } from '@/store/auth'
import { useCartStore } from '@/store/cart'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export default function Header() {
  const router = useRouter()
  const { user, isAuthenticated, logout, fetchMe, hasHydrated, setHasHydrated } = useAuthStore()
  const { items, fetchCart } = useCartStore()
  const { lang, setLang } = useLangStore()
  const [searchQuery, setSearchQuery] = useState('')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  useEffect(() => {
    if (hasHydrated) return
    const initAuth = async () => {
      await useAuthStore.persist.rehydrate()
      setHasHydrated(true)
    }
    initAuth()
  }, [hasHydrated, setHasHydrated])

  useEffect(() => {
    if (hasHydrated) {
      fetchMe()
    }
  }, [hasHydrated, fetchMe])

  useEffect(() => {
    if (hasHydrated && isAuthenticated) {
      fetchCart()
    }
  }, [hasHydrated, isAuthenticated, fetchCart])

  const cartCount = items.reduce((sum, item) => sum + item.quantity, 0)

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      router.push(`/?search=${encodeURIComponent(searchQuery.trim())}`)
    }
  }

  const handleLogout = () => {
    logout()
    router.push('/')
  }

  return (
    <div className="w-full" key={lang}>
      {hasHydrated && isAuthenticated && user && (!user.is_verified || !user.phone_verified) && (
        <div className="bg-yellow-400 text-gray-950 py-2 px-4 text-center text-xs font-bold animate-in fade-in slide-in-from-top duration-500">
          <div className="container flex items-center justify-center gap-4 flex-wrap">
            {!user.is_verified && (
              <div className="flex items-center gap-2">
                <Mail className="h-3 w-3" />
                <span>{t('メールアドレスが未認証です。', lang)}</span>
              </div>
            )}
            {!user.phone_verified && (
              <div className="flex items-center gap-2">
                <Smartphone className="h-3 w-3" />
                <span>{t('電話番号未認証', lang)}</span>
              </div>
            )}
            <Link href="/mypage" className="underline hover:text-gray-800 ml-1">
              {t('マイページで認証してください', lang)}
            </Link>
          </div>
        </div>
      )}
      <header className="sticky top-0 z-50 w-full border-b border-gray-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80">
        <div className="container flex h-16 items-center gap-4">
          <Link href="/" className="flex items-center gap-2 md:gap-3 font-bold mr-2 md:mr-4 group flex-shrink-0">
            <div className="relative h-10 w-10 flex-shrink-0 overflow-hidden rounded-md border border-yellow-400/20">
              <Image
                src="/logo-main.png"
                alt="KRX TCG"
                fill
                className="object-contain"
                priority
              />
            </div>
            <span className="text-luxury-gold tracking-widest text-xl md:text-2xl whitespace-nowrap">KRX TCG</span>
          </Link>

          <form onSubmit={handleSearch} className="hidden md:flex flex-1 max-w-md">
            <div className="relative w-full">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                type="search"
                placeholder={t('カードを検索...', lang)}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 bg-white border-gray-300 text-gray-900 placeholder:text-gray-400 focus:border-yellow-400/50"
              />
            </div>
          </form>

          <div className="flex-1 md:hidden" />

          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="text-gray-600 hover:text-gray-900 hover:bg-gray-100"
              onClick={() => setLang(lang === 'ja' ? 'en' : 'ja')}
              title={lang === 'ja' ? 'Switch to English' : '日本語に切り替え'}
            >
              <Globe className="h-4 w-4 mr-1" />
              <span className="text-xs font-medium">{lang === 'ja' ? 'EN' : 'JP'}</span>
            </Button>

            <Button asChild variant="ghost" size="icon" className="relative text-gray-600 hover:text-gray-900 hover:bg-gray-100">
              <Link href="/cart">
                <ShoppingCart className="h-5 w-5 shrink-0" />
                {cartCount > 0 && (
                  <span className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-yellow-400 text-gray-950 text-xs font-bold flex items-center justify-center">
                    {cartCount > 99 ? '99+' : cartCount}
                  </span>
                )}
              </Link>
            </Button>

            <div className="hidden md:flex items-center gap-2">
              {!hasHydrated ? (
                <div className="h-9 w-24 animate-pulse bg-gray-100 rounded-md" />
              ) : isAuthenticated && user ? (
                <>
                  {user.is_admin && (
                    <Button asChild variant="ghost" size="sm" className="text-yellow-600 hover:text-yellow-500 hover:bg-gray-100">
                      <Link href="/admin">
                        <Shield className="h-4 w-4 shrink-0 mr-1" />
                        {t('管理', lang)}
                      </Link>
                    </Button>
                  )}
                  <Button asChild variant="ghost" size="sm" className="text-gray-600 hover:text-gray-900 hover:bg-gray-100">
                    <Link href="/mypage">
                      <User className="h-4 w-4 shrink-0 mr-1" />
                      {t('マイページ', lang)}
                    </Link>
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleLogout}
                    className="text-gray-600 hover:text-red-500 hover:bg-gray-100"
                  >
                    <LogOut className="h-4 w-4" />
                  </Button>
                </>
              ) : (
                <>
                  <Button asChild variant="ghost" size="sm" className="text-gray-600 hover:text-gray-900 hover:bg-gray-100">
                    <Link href="/login">{t('ログイン', lang)}</Link>
                  </Button>
                  <Button asChild size="sm" className="bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-semibold">
                    <Link href="/register">{t('会員登録', lang)}</Link>
                  </Button>
                </>
              )}
            </div>

            <Button
              variant="ghost"
              size="icon"
              className="md:hidden text-gray-600 hover:text-gray-900 hover:bg-gray-100"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? <X className="h-5 w-5 shrink-0" /> : <Menu className="h-5 w-5 shrink-0" />}
            </Button>
          </div>
        </div>

        {mobileMenuOpen && (
          <div className="md:hidden border-t border-gray-200 bg-white px-4 py-4 space-y-3">
            <form onSubmit={handleSearch} className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  type="search"
                  placeholder={t('カードを検索...', lang)}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 bg-white border-gray-300 text-gray-900 placeholder:text-gray-400"
                />
              </div>
              <Button type="submit" size="sm" className="bg-yellow-400 text-gray-950 hover:bg-yellow-300">
                {t('検索', lang)}
              </Button>
            </form>

            {!hasHydrated ? (
              <div className="h-24 animate-pulse bg-gray-100 rounded-md" />
            ) : isAuthenticated && user ? (
              <div className="flex flex-col gap-2">
                {user.is_admin && (
                  <Button asChild variant="outline" className="w-full border-yellow-400/30 text-yellow-600">
                    <Link href="/admin" onClick={() => setMobileMenuOpen(false)}>
                      <Shield className="h-4 w-4 shrink-0 mr-2" />
                      {t('管理画面', lang)}
                    </Link>
                  </Button>
                )}
                <Button asChild variant="outline" className="w-full border-gray-300 text-gray-700">
                  <Link href="/mypage" onClick={() => setMobileMenuOpen(false)}>
                    <User className="h-4 w-4 shrink-0 mr-2" />
                    {t('マイページ', lang)} ({user.name})
                  </Link>
                </Button>
                <Button
                  variant="outline"
                  className="w-full border-red-300 text-red-500"
                  onClick={() => { handleLogout(); setMobileMenuOpen(false) }}
                >
                  <LogOut className="h-4 w-4 mr-2" />
                  {t('ログアウト', lang)}
                </Button>
              </div>
            ) : (
              <div className="flex gap-2">
                <Button asChild variant="outline" className="flex-1 w-full border-gray-300 text-gray-700">
                  <Link href="/login" onClick={() => setMobileMenuOpen(false)}>
                    {t('ログイン', lang)}
                  </Link>
                </Button>
                <Button asChild className="flex-1 w-full bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-semibold">
                  <Link href="/register" onClick={() => setMobileMenuOpen(false)}>
                    {t('会員登録', lang)}
                  </Link>
                </Button>
              </div>
            )}
          </div>
        )}
      </header>
    </div>
  )
}
