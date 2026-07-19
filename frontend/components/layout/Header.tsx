'use client'

import Link from 'next/link'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { SignedIn, SignedOut, UserButton, useAuth, useClerk } from '@clerk/nextjs'
import { ShoppingCart, Search, User, Shield, Menu, X, Globe, Mail, LogOut, ArrowUpRight } from 'lucide-react'
import { useState, useEffect } from 'react'
import { useBackendAuth } from '@/hooks/useBackendAuth'
import { useAuthStore } from '@/store/auth'
import { useCartStore } from '@/store/cart'
import { useLangStore } from '@/store/lang'
import { useIsAdmin } from '@/hooks/useIsAdmin'
import { t } from '@/lib/i18n'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { BUYLIST_SITE_URL } from '@/lib/site-urls'

export default function Header() {
  const router = useRouter()
  const { signOut } = useClerk()
  const { isSignedIn, isLoaded: clerkLoaded } = useAuth()
  const { user, fetchMe, hasHydrated, setHasHydrated, authProvider, logout } = useAuthStore()
  const { isLoggedIn } = useBackendAuth()
  const isAdmin = useIsAdmin()
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
    if (hasHydrated && isLoggedIn) {
      fetchCart()
    }
  }, [hasHydrated, isLoggedIn, fetchCart])

  const cartCount = items.reduce((sum, item) => sum + item.quantity, 0)

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      router.push(`/?search=${encodeURIComponent(searchQuery.trim())}`)
    }
  }

  const handleMobileLogout = async () => {
    setMobileMenuOpen(false)
    logout()
    try {
      await signOut({ redirectUrl: '/' })
    } catch {
      router.push('/')
    }
  }

  const handleMobileMypage = () => {
    setMobileMenuOpen(false)
    router.push('/mypage')
  }

  const showMobileLoggedIn = clerkLoaded && isLoggedIn

  const showLegacyVerifyBanner =
    hasHydrated &&
    isLoggedIn &&
    user &&
    authProvider !== 'clerk' &&
    !user.is_verified

  return (
    <div className="w-full overflow-x-hidden" key={lang}>
      {showLegacyVerifyBanner && (
        <div className="bg-yellow-400 text-gray-950 py-2 px-4 text-center text-xs font-bold animate-in fade-in slide-in-from-top duration-500">
          <div className="container flex items-center justify-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <Mail className="h-3 w-3" />
              <span>{t('メールアドレスが未認証です。', lang)}</span>
            </div>
            <Link href="/mypage" className="underline hover:text-gray-800 ml-1">
              {t('マイページで認証してください', lang)}
            </Link>
          </div>
        </div>
      )}
      <header className="sticky top-0 z-50 w-full border-b border-gray-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80">
        <div className="container flex h-[3.75rem] sm:h-16 items-center gap-1.5 sm:gap-3 min-w-0 max-w-full">
          <Link href="/" className="flex items-center gap-1.5 sm:gap-2 font-bold mr-1 sm:mr-3 group flex-shrink-0 min-w-0 max-w-[42%] sm:max-w-none">
            <div className="relative h-8 w-8 sm:h-9 sm:w-9 md:h-10 md:w-10 flex-shrink-0 overflow-hidden rounded-md border border-yellow-400/20">
              <Image
                src="/logo-main.png"
                alt="KRX TCG"
                fill
                className="object-contain"
                priority
              />
            </div>
            <div className="flex flex-col min-w-0">
              <span className="header-brand-text text-sm sm:text-base md:text-xl truncate">KRX TCG</span>
              <span className="hidden sm:block text-[10px] md:text-xs text-gray-500 font-medium leading-tight truncate">
                {t('オンラインショップ', lang)}
              </span>
            </div>
          </Link>

          <Button
            asChild
            variant="ghost"
            size="sm"
            className="hidden lg:flex text-gray-600 hover:text-gray-900 hover:bg-gray-100 px-2 h-9 flex-shrink-0"
          >
            <a href={BUYLIST_SITE_URL} target="_blank" rel="noopener noreferrer">
              {t('オンライン買取', lang)}
              <ArrowUpRight className="h-3.5 w-3.5 ml-1 shrink-0" />
            </a>
          </Button>

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

          <div className="flex items-center gap-0.5 sm:gap-1 flex-shrink-0">
            <Button
              variant="ghost"
              size="sm"
              className="text-gray-600 hover:text-gray-900 hover:bg-gray-100 px-1.5 sm:px-2 h-9"
              onClick={() => setLang(lang === 'ja' ? 'en' : 'ja')}
              title={lang === 'ja' ? 'Switch to English' : '日本語に切り替え'}
            >
              <Globe className="h-4 w-4 mr-1" />
              <span className="text-xs font-medium">{lang === 'ja' ? 'EN' : 'JP'}</span>
            </Button>

            <Button asChild variant="ghost" size="icon" className="relative text-gray-600 hover:text-gray-900 hover:bg-gray-100 h-9 w-9">
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
              ) : (
                <>
                  <SignedIn>
                    {isAdmin && (
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
                    <UserButton
                      afterSignOutUrl="/"
                      appearance={{
                        elements: {
                          avatarBox: 'h-9 w-9',
                        },
                      }}
                    />
                  </SignedIn>
                  <SignedOut>
                    <Button asChild variant="ghost" size="sm" className="text-gray-600 hover:text-gray-900 hover:bg-gray-100">
                      <Link href="/sign-in">{t('ログイン', lang)}</Link>
                    </Button>
                    <Button asChild size="sm" className="bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-semibold">
                      <Link href="/sign-up">{t('会員登録', lang)}</Link>
                    </Button>
                  </SignedOut>
                </>
              )}
            </div>

            <Button
              variant="ghost"
              size="icon"
              className="md:hidden text-gray-600 hover:text-gray-900 hover:bg-gray-100 h-9 w-9"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              {mobileMenuOpen ? <X className="h-5 w-5 shrink-0" /> : <Menu className="h-5 w-5 shrink-0" />}
            </Button>
          </div>
        </div>

        {mobileMenuOpen && (
          <div className="md:hidden border-t border-gray-200 bg-white px-4 py-4 space-y-3 overflow-x-hidden">
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

            <Button asChild variant="outline" className="w-full border-gray-300 text-gray-700">
              <a href={BUYLIST_SITE_URL} target="_blank" rel="noopener noreferrer">
                {t('オンライン買取', lang)}
                <ArrowUpRight className="h-4 w-4 shrink-0 ml-2" />
              </a>
            </Button>

            {!hasHydrated || !clerkLoaded ? (
              <div className="h-24 animate-pulse bg-gray-100 rounded-md" />
            ) : showMobileLoggedIn ? (
              <div className="flex flex-col gap-2">
                {isAdmin && (
                  <Button asChild variant="outline" className="w-full border-yellow-400/30 text-yellow-600">
                    <Link href="/admin" onClick={() => setMobileMenuOpen(false)}>
                      <Shield className="h-4 w-4 shrink-0 mr-2" />
                      {t('管理画面', lang)}
                    </Link>
                  </Button>
                )}
                <Button
                  variant="outline"
                  className="w-full border-gray-300 text-gray-700"
                  onClick={handleMobileMypage}
                >
                  <User className="h-4 w-4 shrink-0 mr-2" />
                  {t('マイページ', lang)}{user?.name ? ` (${user.name})` : ''}
                </Button>
                <Button
                  variant="outline"
                  className="w-full border-gray-300 text-gray-700"
                  onClick={handleMobileLogout}
                >
                  <LogOut className="h-4 w-4 shrink-0 mr-2" />
                  {t('ログアウト', lang)}
                </Button>
              </div>
            ) : (
              <div className="flex gap-2">
                <Button asChild variant="outline" className="flex-1 w-full border-gray-300 text-gray-700">
                  <Link href="/sign-in" onClick={() => setMobileMenuOpen(false)}>
                    {t('ログイン', lang)}
                  </Link>
                </Button>
                <Button asChild className="flex-1 w-full bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-semibold">
                  <Link href="/sign-up" onClick={() => setMobileMenuOpen(false)}>
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
