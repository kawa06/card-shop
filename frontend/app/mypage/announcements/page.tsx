'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'
import { ArrowLeft, Bell, Search } from 'lucide-react'
import { announcementsApi } from '@/lib/api'
import { Announcement } from '@/lib/types'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { useAuthStore } from '@/store/auth'
import { Input } from '@/components/ui/input'
import AnnouncementCard from '@/components/announcements/AnnouncementCard'

export default function AnnouncementsListPage() {
  const router = useRouter()
  const { isSignedIn, isLoaded } = useAuth()
  const { isAuthenticated, hasHydrated } = useAuthStore()
  const { lang } = useLangStore()
  const [items, setItems] = useState<Announcement[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)

  const fetchFeed = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await announcementsApi.getFeed({ lang, q: query || undefined })
      setItems(res.data.items || [])
      setUnreadCount(res.data.unread_count || 0)
    } catch {
      setItems([])
    } finally {
      setIsLoading(false)
    }
  }, [lang, query])

  useEffect(() => {
    if (!isLoaded || !hasHydrated) return
    if (!isSignedIn && !isAuthenticated) {
      router.push('/sign-in')
      return
    }
    fetchFeed()
  }, [isLoaded, hasHydrated, isSignedIn, isAuthenticated, router, fetchFeed])

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-3xl">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/mypage" className="text-gray-400 hover:text-gray-900">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <Bell className="h-6 w-6 text-yellow-500" />
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-gray-900">{t('お知らせ', lang)}</h1>
            {unreadCount > 0 && (
              <p className="text-sm text-yellow-700 mt-0.5">
                {lang === 'ja' ? `未読 ${unreadCount}件` : `${unreadCount} unread`}
              </p>
            )}
          </div>
        </div>

        <form
          className="relative mb-6"
          onSubmit={(event) => {
            event.preventDefault()
            setQuery(search.trim())
          }}
        >
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={lang === 'ja' ? 'タイトル・本文で検索' : 'Search title or content'}
            className="pl-9 bg-gray-50 border-gray-200"
          />
        </form>

        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-28 rounded-xl bg-gray-100 animate-pulse" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-200 p-10 text-center text-gray-500">
            {lang === 'ja' ? 'お知らせはありません' : 'No announcements yet'}
          </div>
        ) : (
          <div className="space-y-4">
            {items.map((item) => (
              <AnnouncementCard key={item.id} item={item} href={`/mypage/announcements/${item.id}`} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
