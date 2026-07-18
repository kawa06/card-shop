'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'
import { ArrowLeft, Heart } from 'lucide-react'
import { useBackendAuth } from '@/hooks/useBackendAuth'
import { favoritesApi } from '@/lib/api'
import { Favorite } from '@/lib/types'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import CardCard from '@/components/cards/CardCard'

export default function FavoritesPage() {
  const router = useRouter()
  const { isSignedIn } = useAuth()
  const { isLoggedIn, isReady, requireAuth } = useBackendAuth()
  const { lang } = useLangStore()
  const [favorites, setFavorites] = useState<Favorite[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  useEffect(() => {
    if (!isMounted || !isReady) return
    if (!isLoggedIn) {
      router.push('/sign-in')
      return
    }

    void requireAuth()
      .then((token) => {
        if (!token) {
          router.push('/sign-in')
          return null
        }
        return favoritesApi.getAll()
      })
      .then((res) => {
        if (res) setFavorites(res.data || [])
      })
      .catch(() => setFavorites([]))
      .finally(() => setIsLoading(false))
  }, [isMounted, isReady, isLoggedIn, isSignedIn, router, requireAuth])

  if (!isMounted || !isReady || !isLoggedIn) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-5xl">
        <Link
          href="/mypage"
          className="inline-flex items-center gap-2 text-gray-400 hover:text-gray-900 mb-6 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('マイページ', lang)}
        </Link>

        <h1 className="text-2xl font-bold text-gray-900 mb-2 flex items-center gap-2">
          <Heart className="h-6 w-6 text-pink-400" />
          {t('お気に入り', lang)}
        </h1>
        <p className="text-sm text-gray-500 mb-8">
          {isLoading
            ? t('読み込み中...', lang)
            : lang === 'ja'
              ? `${favorites.length}件のお気に入り`
              : `${favorites.length} favorites`}
        </p>

        {isLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="aspect-[3/4] bg-gray-100 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : favorites.length === 0 ? (
          <div className="text-center py-16 bg-gray-50 rounded-xl border border-gray-200">
            <Heart className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-600 mb-4">{t('お気に入りはありません', lang)}</p>
            <Link href="/" className="text-yellow-500 hover:text-yellow-400 text-sm font-medium">
              {t('ショップを見る', lang)} →
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {favorites.map((fav) => (
              <CardCard key={fav.id} card={fav.card} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
