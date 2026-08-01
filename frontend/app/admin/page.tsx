'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
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
  FileSpreadsheet,
  Settings,
  MessageSquare,
  Banknote,
  Shield,
  Lock,
  UserCheck,
} from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { cardsApi, ordersApi, categoriesApi, announcementsApi, adminApi, shippingApi, packsApi, adminInquiriesApi, adminBuybackApi } from '@/lib/api'

interface Stats {
  cards: number
  orders: number
  categories: number
  packs: number
  announcements: number
  users: number
  shipping: number
  inquiryUnreplied: number
  buybackPendingKyc: number
  buybackSubmittedRequests: number
  buybackPayoutPending: number
}

export default function AdminPage() {
  const { lang } = useLangStore()
  const { isReady } = useAdminGuard()
  const { hasPermission, session } = useAdminPermissions()
  const [stats, setStats] = useState<Stats>({ cards: 0, orders: 0, categories: 0, packs: 0, announcements: 0, users: 0, shipping: 0, inquiryUnreplied: 0, buybackPendingKyc: 0, buybackSubmittedRequests: 0, buybackPayoutPending: 0 })
  const [isLoading, setIsLoading] = useState(true)
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  useEffect(() => {
    if (!isMounted || !isReady) return

    Promise.allSettled([
      cardsApi.getAll({ size: 1 }),
      ordersApi.getAll(),
      categoriesApi.getAll(),
      packsApi.getAll(),
      announcementsApi.getAll(),
      adminApi.getAllUsers(),
      shippingApi.getRates(),
      adminInquiriesApi.getStats(),
      adminBuybackApi.getStats(),
    ]).then(([cardsRes, ordersRes, catsRes, packsRes, annsRes, usersRes, shippingRes, inquiryRes, buybackRes]) => {
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
        inquiryUnreplied:
          inquiryRes.status === 'fulfilled' ? inquiryRes.value.data.unreplied_count : 0,
        buybackPendingKyc:
          buybackRes.status === 'fulfilled' ? buybackRes.value.data.pending_kyc_count : 0,
        buybackSubmittedRequests:
          buybackRes.status === 'fulfilled' ? buybackRes.value.data.submitted_request_count : 0,
        buybackPayoutPending:
          buybackRes.status === 'fulfilled' ? buybackRes.value.data.payout_pending_count : 0,
      })
    }).finally(() => setIsLoading(false))
  }, [isMounted, isReady])

  if (!isMounted || !isReady) return null

  const shopRoles = new Set(['owner', 'admin', 'sales_manager'])
  const canSeeShop = !!session?.role_code && shopRoles.has(session.role_code)

  const sections = [
    ...(canSeeShop
      ? [
          { href: '/admin/cards', icon: CreditCard, label: t('カード管理', lang), count: stats.cards, color: 'text-yellow-400', bg: 'bg-yellow-400/10 border-yellow-400/20' },
          { href: '/admin/packs', icon: Package, label: t('パック管理', lang), count: stats.packs, color: 'text-sky-400', bg: 'bg-sky-400/10 border-sky-400/20' },
          { href: '/admin/categories', icon: Tag, label: t('カテゴリー管理', lang), count: stats.categories, color: 'text-blue-400', bg: 'bg-blue-400/10 border-blue-400/20' },
          { href: '/admin/orders', icon: ShoppingBag, label: t('注文管理', lang), count: stats.orders, color: 'text-green-400', bg: 'bg-green-400/10 border-green-400/20' },
          { href: '/admin/inquiries', icon: MessageSquare, label: '問い合わせ管理', count: stats.inquiryUnreplied, color: 'text-teal-500', bg: 'bg-teal-500/10 border-teal-500/20' },
          { href: '/admin/click-post', icon: FileSpreadsheet, label: 'クリックポストCSV', count: stats.orders, color: 'text-amber-500', bg: 'bg-amber-500/10 border-amber-500/20' },
          { href: '/admin/announcements', icon: Bell, label: t('お知らせ管理', lang), count: stats.announcements, color: 'text-purple-400', bg: 'bg-purple-400/10 border-purple-400/20' },
          { href: '/admin/users', icon: Users, label: t('ユーザー管理', lang), count: stats.users, color: 'text-pink-400', bg: 'bg-pink-400/10 border-pink-400/20' },
          { href: '/admin/shipping', icon: Truck, label: t('送料管理', lang), count: stats.shipping || 0, color: 'text-orange-400', bg: 'bg-orange-400/10 border-orange-400/20' },
          { href: '/admin/settings/invoice', icon: Settings, label: 'インボイス設定', count: 0, color: 'text-gray-600', bg: 'bg-gray-100 border-gray-200' },
        ]
      : []),
    ...(hasPermission('buyback.catalog.read')
      ? [{ href: '/admin/buyback/catalog', icon: CreditCard, label: '買取カタログ管理', count: 0, color: 'text-lime-600', bg: 'bg-lime-500/10 border-lime-500/20' }]
      : []),
    ...(hasPermission('buyback.settings.read')
      ? [{ href: '/admin/buyback/settings', icon: Settings, label: '買取チャネル設定', count: 0, color: 'text-violet-600', bg: 'bg-violet-500/10 border-violet-500/20' }]
      : []),
    ...(hasPermission('buyback.settings.read')
      ? [{ href: '/admin/buyback/banners', icon: Bell, label: '限定価格バナー', count: 0, color: 'text-rose-600', bg: 'bg-rose-500/10 border-rose-500/20' }]
      : []),
    ...(hasPermission('buyback.reservation.read')
      ? [{ href: '/admin/buyback/reservations', icon: Package, label: '店舗買取予約', count: 0, color: 'text-indigo-600', bg: 'bg-indigo-500/10 border-indigo-500/20' }]
      : []),
    ...(hasPermission('buyback.identity.read')
      ? [{ href: '/admin/buyback/kyc', icon: UserCheck, label: '買取 KYC 審査', count: stats.buybackPendingKyc, color: 'text-orange-500', bg: 'bg-orange-500/10 border-orange-500/20' }]
      : []),
    ...(hasPermission('buyback.receive')
      ? [{ href: '/admin/buyback/receiving', icon: Package, label: '買取荷物受付', count: stats.buybackSubmittedRequests, color: 'text-yellow-600', bg: 'bg-yellow-500/10 border-yellow-500/20' }]
      : []),
    ...(hasPermission('buyback.ship.read')
      ? [{ href: '/admin/buyback/shipping-verify', icon: Truck, label: '発送前確認', count: 0, color: 'text-sky-600', bg: 'bg-sky-500/10 border-sky-500/20' }]
      : []),
    ...(hasPermission('buyback.print.internal')
      ? [{ href: '/admin/buyback/labels', icon: FileSpreadsheet, label: '買取ラベルCSV', count: 0, color: 'text-teal-600', bg: 'bg-teal-500/10 border-teal-500/20' }]
      : []),
    ...(hasPermission('buyback.logs.read')
      ? [{ href: '/admin/buyback/logs', icon: Shield, label: '買取物流ログ', count: 0, color: 'text-slate-600', bg: 'bg-slate-500/10 border-slate-500/20' }]
      : []),
    ...(hasPermission('buyback.request.read')
      ? [{ href: '/admin/buyback/requests', icon: Package, label: '買取申込管理', count: stats.buybackSubmittedRequests, color: 'text-amber-600', bg: 'bg-amber-500/10 border-amber-500/20' }]
      : []),
    ...(hasPermission('buyback.payout.complete')
      ? [{ href: '/admin/buyback/payouts', icon: Banknote, label: '買取振込管理', count: stats.buybackPayoutPending, color: 'text-emerald-600', bg: 'bg-emerald-500/10 border-emerald-500/20' }]
      : []),
    ...(hasPermission('admin.users.read')
      ? [{ href: '/admin/security/admins', icon: Lock, label: '管理者・セキュリティ', count: 0, color: 'text-red-500', bg: 'bg-red-500/10 border-red-500/20' }]
      : []),
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
