'use client'

import { Heart } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useAuthStore } from '@/store/auth'
import { useFavoritesStore } from '@/store/favorites'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { toast } from '@/lib/use-toast'

interface FavoriteButtonProps {
  cardId: number
  size?: 'sm' | 'md'
  className?: string
}

export default function FavoriteButton({ cardId, size = 'md', className = '' }: FavoriteButtonProps) {
  const router = useRouter()
  const { isSignedIn, isLoaded: isClerkLoaded } = useAuth()
  const { isAuthenticated, ensureBackendAuth, hasHydrated, setHasHydrated } = useAuthStore()
  const { lang } = useLangStore()
  const { loaded, fetchIds, toggle, isFavorite } = useFavoritesStore()
  const [isToggling, setIsToggling] = useState(false)

  useEffect(() => {
    if (hasHydrated) return
    const initAuth = async () => {
      await useAuthStore.persist.rehydrate()
      setHasHydrated(true)
    }
    void initAuth()
  }, [hasHydrated, setHasHydrated])

  const isLoggedIn = isSignedIn || isAuthenticated

  useEffect(() => {
    if (!hasHydrated || !isClerkLoaded || !isLoggedIn || loaded) return
    void ensureBackendAuth()
      .then((token) => {
        if (token) return fetchIds()
      })
      .catch(() => {})
  }, [hasHydrated, isClerkLoaded, isLoggedIn, loaded, ensureBackendAuth, fetchIds])

  const favorite = isFavorite(cardId)
  const iconSize = size === 'sm' ? 'h-4 w-4' : 'h-5 w-5'
  const buttonSize = size === 'sm' ? 'p-1.5' : 'p-2'

  const handleClick = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()

    if (!isClerkLoaded || !hasHydrated) return

    if (!isLoggedIn) {
      toast({
        title: t('ログインが必要です', lang),
        description: t('お気に入りに追加するにはログインしてください', lang),
        variant: 'destructive',
      })
      router.push('/sign-in')
      return
    }

    setIsToggling(true)
    try {
      const token = await ensureBackendAuth()
      if (!token) {
        toast({
          title: t('ログインが必要です', lang),
          description: t('お気に入りに追加するにはログインしてください', lang),
          variant: 'destructive',
        })
        router.push('/sign-in')
        return
      }

      if (!loaded) {
        await fetchIds()
      }

      const added = await toggle(cardId)
      toast({
        title: added ? t('お気に入りに追加しました', lang) : t('お気に入りから削除しました', lang),
      })
    } catch {
      toast({
        title: t('エラー', lang),
        description: t('お気に入りの更新に失敗しました', lang),
        variant: 'destructive',
      })
    } finally {
      setIsToggling(false)
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={isToggling}
      aria-label={favorite ? t('お気に入りから削除', lang) : t('お気に入りに追加', lang)}
      className={`rounded-full border transition-colors disabled:opacity-50 ${buttonSize} ${
        favorite
          ? 'border-pink-400 bg-pink-50 text-pink-500 hover:bg-pink-100'
          : 'border-gray-200 bg-white text-gray-400 hover:border-pink-300 hover:text-pink-400'
      } ${className}`}
    >
      <Heart className={`${iconSize} ${favorite ? 'fill-current' : ''}`} />
    </button>
  )
}
