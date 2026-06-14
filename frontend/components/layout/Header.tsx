'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ShoppingCart, Search, User, LogOut, Shield, Menu, X } from 'lucide-react'
import { useState, useEffect } from 'react'
import { useAuthStore } from '@/store/auth'
import { useCartStore } from '@/store/cart'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

export default function Header() {
  const router = useRouter()
  const { user, isAuthenticated, logout } = useAuthStore()
  const { items, fetchCart } = useCartStore()
  const [searchQuery, setSearchQuery] = useState('')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  useEffect(() => {
    if (isAuthenticated) {
      fetchCart()
    }
  }, [isAuthenticated, fetchCart])

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
    <header className="sticky top-0 z-50 w-full border-b border-white/10 bg-gray-950/95 backdrop-blur supports-[backdrop-filter]:bg-gray-950/60">
      <div className="container flex h-16 items-center gap-4">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 font-bold text-xl mr-4">
          <span className="text-yellow-400">✦</span>
          <span className="text-white">Oripa_kawa</span>
        </Link>

        {/* Search - desktop */}
        <form onSubmit={handleSearch} className="hidden md:flex flex-1 max-w-md">
          <div className="relative w-full">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              type="search"
              placeholder="カードを検索..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 bg-gray-900 border-gray-700 text-white placeholder:text-gray-500 focus:border-yellow-400/50"
            />
          </div>
        </form>

        <div className="flex-1 md:hidden" />

        {/* Actions */}
        <div className="flex items-center gap-2">
          {/* Cart */}
          <Link href="/cart">
            <Button variant="ghost" size="icon" className="relative text-gray-300 hover:text-white hover:bg-white/10">
              <ShoppingCart className="h-5 w-5" />
              {cartCount > 0 && (
                <span className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-yellow-400 text-gray-950 text-xs font-bold flex items-center justify-center">
                  {cartCount > 99 ? '99+' : cartCount}
                </span>
              )}
            </Button>
          </Link>

          {/* Auth - desktop */}
          <div className="hidden md:flex items-center gap-2">
            {isAuthenticated && user ? (
              <>
                {user.is_admin && (
                  <Link href="/admin">
                    <Button variant="ghost" size="sm" className="text-yellow-400 hover:text-yellow-300 hover:bg-white/10">
                      <Shield className="h-4 w-4 mr-1" />
                      管理
                    </Button>
                  </Link>
                )}
                <Link href="/mypage">
                  <Button variant="ghost" size="sm" className="text-gray-300 hover:text-white hover:bg-white/10">
                    <User className="h-4 w-4 mr-1" />
                    {user.name}
                  </Button>
                </Link>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleLogout}
                  className="text-gray-300 hover:text-red-400 hover:bg-white/10"
                >
                  <LogOut className="h-4 w-4" />
                </Button>
              </>
            ) : (
              <>
                <Link href="/login">
                  <Button variant="ghost" size="sm" className="text-gray-300 hover:text-white hover:bg-white/10">
                    ログイン
                  </Button>
                </Link>
                <Link href="/register">
                  <Button size="sm" className="bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-semibold">
                    会員登録
                  </Button>
                </Link>
              </>
            )}
          </div>

          {/* Mobile menu toggle */}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden text-gray-300 hover:text-white hover:bg-white/10"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-white/10 bg-gray-950 px-4 py-4 space-y-3">
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                type="search"
                placeholder="カードを検索..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 bg-gray-900 border-gray-700 text-white placeholder:text-gray-500"
              />
            </div>
            <Button type="submit" size="sm" className="bg-yellow-400 text-gray-950 hover:bg-yellow-300">
              検索
            </Button>
          </form>

          {isAuthenticated && user ? (
            <div className="flex flex-col gap-2">
              {user.is_admin && (
                <Link href="/admin" onClick={() => setMobileMenuOpen(false)}>
                  <Button variant="outline" className="w-full border-yellow-400/30 text-yellow-400">
                    <Shield className="h-4 w-4 mr-2" />
                    管理画面
                  </Button>
                </Link>
              )}
              <Link href="/mypage" onClick={() => setMobileMenuOpen(false)}>
                <Button variant="outline" className="w-full border-white/20 text-gray-300">
                  <User className="h-4 w-4 mr-2" />
                  マイページ ({user.name})
                </Button>
              </Link>
              <Button
                variant="outline"
                className="w-full border-red-500/30 text-red-400"
                onClick={() => { handleLogout(); setMobileMenuOpen(false) }}
              >
                <LogOut className="h-4 w-4 mr-2" />
                ログアウト
              </Button>
            </div>
          ) : (
            <div className="flex gap-2">
              <Link href="/login" onClick={() => setMobileMenuOpen(false)} className="flex-1">
                <Button variant="outline" className="w-full border-white/20 text-gray-300">
                  ログイン
                </Button>
              </Link>
              <Link href="/register" onClick={() => setMobileMenuOpen(false)} className="flex-1">
                <Button className="w-full bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-semibold">
                  会員登録
                </Button>
              </Link>
            </div>
          )}
        </div>
      )}
    </header>
  )
}
