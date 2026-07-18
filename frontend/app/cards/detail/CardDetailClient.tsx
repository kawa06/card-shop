'use client'

import { useState, useEffect } from 'react'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { ArrowLeft, ShoppingCart, ZoomIn, Package } from 'lucide-react'
import { cardsApi, cardsApi as relatedApi } from '@/lib/api'
import { Card } from '@/lib/types'
import { useBackendAuth } from '@/hooks/useBackendAuth'
import { useCartStore } from '@/store/cart'
import { usePrice } from '@/lib/format'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { toast } from '@/lib/use-toast'
import { Button } from '@/components/ui/button'
import CardCard from '@/components/cards/CardCard'

const rarityColors: Record<string, string> = {
  C:    'bg-gray-500/20 text-gray-600 border-gray-500/40',
  U:    'bg-green-500/20 text-green-300 border-green-500/40',
  R:    'bg-blue-500/20 text-blue-300 border-blue-500/40',
  RR:   'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
  AR:   'bg-teal-500/20 text-teal-300 border-teal-500/40',
  SR:   'bg-purple-500/20 text-purple-300 border-purple-500/40',
  SAR:  'bg-violet-500/20 text-violet-300 border-violet-500/40',
  MUR:  'bg-orange-500/20 text-orange-300 border-orange-500/40',
  SSR:  'bg-pink-500/20 text-pink-300 border-pink-500/40',
  ミラー: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  MA: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
  PROMO: 'bg-red-500/20 text-red-300 border-red-500/40',
  CLASSIC: 'bg-stone-500/20 text-stone-300 border-stone-500/40',
  パック: 'bg-sky-500/20 text-sky-300 border-sky-500/40',
  BOX: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  PSA10: 'bg-zinc-500/20 text-zinc-300 border-zinc-500/40',
}

export default function CardDetailClient({ id }: { id: string }) {
  const router = useRouter()
  const { isLoggedIn, isReady, requireAuth } = useBackendAuth()
  const { addItem } = useCartStore()
  const { formatPrice } = usePrice()
  const { lang } = useLangStore()

  const [card, setCard] = useState<Card | null>(null)
  const [relatedCards, setRelatedCards] = useState<Card[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [quantity, setQuantity] = useState(1)
  const [isZoomed, setIsZoomed] = useState(false)
  const [addingToCart, setAddingToCart] = useState(false)

  useEffect(() => {
    const fetchCard = async () => {
      try {
        const res = await cardsApi.getById(parseInt(id))
        setCard(res.data)
        if (res.data.category_id) {
          const relRes = await relatedApi.getAll({
            category_id: res.data.category_id,
            size: 5,
          })
          const data = relRes.data
          const items = Array.isArray(data) ? data : (data.items || [])
          setRelatedCards(items.filter((c: Card) => c.id !== res.data.id).slice(0, 4))
        }
      } catch {
        router.push('/')
      } finally {
        setIsLoading(false)
      }
    }
    fetchCard()
  }, [id, router])

  const handleAddToCart = async () => {
    if (!isReady) return
    if (!isLoggedIn) {
      toast({
        title: t('ログインが必要です', lang),
        description: t('カートに追加するにはログインしてください', lang),
        variant: 'destructive',
      })
      router.push('/sign-in')
      return
    }
    if (!card || card.stock === 0) return
    setAddingToCart(true)
    try {
      const token = await requireAuth()
      if (!token) {
        toast({
          title: t('ログインが必要です', lang),
          description: t('カートに追加するにはログインしてください', lang),
          variant: 'destructive',
        })
        router.push('/sign-in')
        return
      }
      await addItem(card.id, quantity)
      toast({
        title: 'カートに追加しました',
        description: `${card.name} x${quantity}をカートに追加しました`,
      })
    } catch {
      toast({
        title: 'エラー',
        description: 'カートへの追加に失敗しました',
        variant: 'destructive',
      })
    } finally {
      setAddingToCart(false)
    }
  }

  if (isLoading) {
    return (
      <div className="container py-8 animate-pulse">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="aspect-[3/4] bg-gray-200 rounded-lg" />
          <div className="space-y-4">
            <div className="h-8 bg-gray-200 rounded w-3/4" />
            <div className="h-6 bg-gray-200 rounded w-1/4" />
            <div className="h-20 bg-gray-200 rounded" />
            <div className="h-12 bg-gray-200 rounded" />
          </div>
        </div>
      </div>
    )
  }

  if (!card) return null

  const rarityClass = rarityColors[card.rarity] || rarityColors['C']

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-6">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-gray-400 hover:text-gray-900 mb-6 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          戻る
        </button>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
          <div className="relative">
            <div
              className="relative aspect-[3/4] overflow-hidden rounded-lg border border-gray-200 bg-gray-50 cursor-zoom-in"
              onClick={() => setIsZoomed(true)}
            >
              {card.image_url ? (
                <Image
                  src={card.image_url}
                  alt={card.name}
                  fill
                  className="object-cover"
                  sizes="(max-width: 768px) 100vw, 50vw"
                />
              ) : (
                <div className="flex items-center justify-center h-full">
                  <span className="text-8xl opacity-20">🃏</span>
                </div>
              )}
              <div className="absolute bottom-3 right-3 bg-black/50 rounded-full p-2">
                <ZoomIn className="h-4 w-4 text-white" />
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div>
              {card.category && (
                <p className="text-sm text-gray-500 mb-1">{card.category.name}</p>
              )}
              <h1 className="text-3xl font-bold text-gray-900 mb-2">{card.name}</h1>
              <span className={`inline-block text-sm font-bold px-3 py-1 rounded border ${rarityClass}`}>
                {card.rarity}
              </span>
            </div>

            <div className="flex items-center gap-4">
              <span className="text-4xl font-bold text-yellow-400">
                {formatPrice(card.price)}
              </span>
              <div className="flex items-center gap-1 text-sm text-gray-400">
                <Package className="h-4 w-4" />
                <span>残り {card.stock}枚</span>
              </div>
            </div>

            {card.description && (
              <p className="text-gray-600 leading-relaxed border-t border-gray-200 pt-4">
                {card.description}
              </p>
            )}

            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <span className="text-sm text-gray-400">数量:</span>
                <div className="flex items-center border border-gray-300 rounded-md overflow-hidden">
                  <button
                    onClick={() => setQuantity(Math.max(1, quantity - 1))}
                    className="px-3 py-2 text-gray-600 hover:bg-gray-100 transition-colors disabled:opacity-30"
                    disabled={quantity <= 1}
                  >
                    -
                  </button>
                  <span className="px-4 py-2 text-gray-900 min-w-[3rem] text-center">{quantity}</span>
                  <button
                    onClick={() => setQuantity(Math.min(card.stock, quantity + 1))}
                    className="px-3 py-2 text-gray-600 hover:bg-gray-100 transition-colors disabled:opacity-30"
                    disabled={quantity >= card.stock}
                  >
                    +
                  </button>
                </div>
              </div>

              <Button
                onClick={handleAddToCart}
                disabled={card.stock === 0 || addingToCart}
                className="w-full h-12 bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold text-base disabled:opacity-50"
              >
                <ShoppingCart className="h-5 w-5 mr-2" />
                {card.stock === 0 ? '在庫なし' : addingToCart ? '追加中...' : 'カートに入れる'}
              </Button>
            </div>
          </div>
        </div>

        {relatedCards.length > 0 && (
          <div>
            <h2 className="text-xl font-bold text-gray-900 mb-4">関連カード</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {relatedCards.map((rc) => (
                <CardCard key={rc.id} card={rc} />
              ))}
            </div>
          </div>
        )}
      </div>

      {isZoomed && card.image_url && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center cursor-zoom-out p-4"
          onClick={() => setIsZoomed(false)}
        >
          <div className="relative max-w-2xl w-full max-h-[90vh]">
            <Image
              src={card.image_url}
              alt={card.name}
              width={800}
              height={1100}
              className="object-contain w-full h-full"
            />
          </div>
        </div>
      )}
    </div>
  )
}
