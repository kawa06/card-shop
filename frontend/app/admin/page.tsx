'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  LayoutDashboard,
  CreditCard,
  Tag,
  ShoppingBag,
  Bell,
  Users,
  ChevronRight,
  Truck,
  Package,
} from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { cardsApi, ordersApi, categoriesApi, announcementsApi, adminApi, shippingApi, packsApi } from '@/lib/api'

interface Stats {
  cards: number
  orders: number
  categories: number
  packs: number
  announcements: number
  users: number
  shipping: number
}

export default function AdminPage() {
  const router = useRouter()
  const { isAuthenticated, user, isLoading: isAuthLoading } = useAuthStore()
  const { lang } = useLangStore()
  const [stats, setStats] = useState<Stats>({ cards: 0, orders: 0, categories: 0, packs: 0, announcements: 0, users: 0, shipping: 0 })
  const [isLoading, setIsLoading] = useState(true)
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  useEffect(() => {
    if (!isMounted || isAuthLoading) return

    if (!isAuthenticated) { router.push('/login'); return }
    if (user && !user.is_admin) { router.push('/'); return }

    Promise.allSettled([
      cardsApi.getAll({ size: 1 }),
      ordersApi.getAll(),
      categoriesApi.getAll(),
      packsApi.getAll(),
      announcementsApi.getAll(),
      adminApi.getAllUsers(),
      shippingApi.getRates(),
    ]).then(([cardsRes, ordersRes, catsRes, packsRes, annsRes, usersRes, shippingRes]) => {
      const getCount = (res: PromiseSettledResult<{ data: unknown }>, key = 'length') => {
        if (res.status === 'fulfilled') {
          const d = res.value.data
          if (Array.isArray(d)) return d.length
          if (d && typeof d === 'object' && 'total' in d) return (d as { total: number }).total
        }
        return 0
      }
      setStats({
        cards: getCount(cardsRes),
        orders: getCount(ordersRes),
        categories: getCount(catsRes),
        packs: getCount(packsRes),
        announcements: getCount(annsRes),
        users: getCount(usersRes),
        shipping: getCount(shippingRes),
      })
    }).finally(() => setIsLoading(false))
  }, [isMounted, isAuthLoading, isAuthenticated, user, router])

  if (!isMounted || !isAuthenticated || (user && !user.is_admin)) return null

  const sections = [
    { href: '/admin/cards', icon: CreditCard, label: t('カード管理', lang), count: stats.cards, color: 'text-yellow-400', bg: 'bg-yellow-400/10 border-yellow-400/20' },
    { href: '/admin/packs', icon: Package, label: t('パック管理', lang), count: stats.packs, color: 'text-sky-400', bg: 'bg-sky-400/10 border-sky-400/20' },
    { href: '/admin/categories', icon: Tag, label: t('カテゴリー管理', lang), count: stats.categories, color: 'text-blue-400', bg: 'bg-blue-400/10 border-blue-400/20' },
    { href: '/admin/orders', icon: t('注文管理', lang), label: t('注文管理', lang), count: stats.orders, color: 'text-green-400', bg: 'bg-green-400/10 border-green-400/20' },
    { href: '/admin/announcements', icon: Bell, label: t('お知らせ管理', lang), count: stats.announcements, color: 'text-purple-400', bg: 'bg-purple-400/10 border-purple-400/20' },
    { href: '/admin/users', icon: Users, label: t('ユーザー管理', lang), count: stats.users, color: 'text-pink-400', bg: 'bg-pink-400/10 border-pink-400/20' },
    { href: '/admin/shipping', icon: Truck, label: t('送料管理', lang), count: stats.shipping || 0, color: 'text-orange-400', bg: 'bg-orange-400/10 border-orange-400/20' },
  ]

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-5xl">
        <div className="flex items-center gap-3 mb-8">
          <LayoutDashboard className="h-6 w-6 text-yellow-400" />
          <h1 className="text-2xl font-bold text-gray-900">{t('管理ダッシュボード', lang)}</h1>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {sections.map(({ href, icon: Icon, label, count, color, bg }) => (
            <Link key={href} href={href}>
              <div className={`rounded-xl border ${bg} p-6 hover:scale-[1.02] transition-transform cursor-pointer`}>
                <div className="flex items-center justify-between mb-4">
                  <Icon className={`h-8 w-8 ${color}`} />
                  <ChevronRight className="h-4 w-4 text-gray-500" />
                </div>
                <p className="text-gray-400 text-sm">{label}</p>
                {isLoading ? (
                  <div className="h-8 w-16 bg-gray-200 rounded animate-pulse mt-1" />
                ) : (
                  <p className={`text-3xl font-bold mt-1 ${color}`}>{count}</p>
                )}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
