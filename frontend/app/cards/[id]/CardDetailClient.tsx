'use client'

import { useState, useEffect, useCallback } from 'react'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { ArrowLeft, ShoppingCart, ZoomIn, Package, ChevronLeft, ChevronRight, X } from 'lucide-react'
import { cardsApi } from '@/lib/api'
import { Card } from '@/lib/types'
import { useAuthStore } from '@/store/auth'
import { useCartStore } from '@/store/cart'
import { useLangStore } from '@/store/lang'
import { toast } from '@/lib/use-toast'
import { t } from '@/lib/i18n'
import { useTranslation } from '@/hooks/useTranslation'
import { Button } from '@/components/ui/button'
import CardCard from '@/components/cards/CardCard'

const rarityColors: Record<string, string> = {
  C:    'bg-gray-500/20 text-gray-300 border-gray-500/40',
  U:    'bg-green-500/20 text-green-300 border-green-500/40',
  R:    'bg-blue-500/20 text-blue-300 border-blue-500/40',
  RR:   'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
  AR:   'bg-teal-500/20 text-teal-300 border-teal-500/40',
  SR:   'bg-purple-500/20 text-purple-300 border-purple-500/40',
  SAR:  'bg-violet-500/20 text-violet-300 border-violet-500/40',
  MUR:  'bg-orange-500/20 text-orange-300 border-orange-500/40',
  SSR:  'bg-pink-500/20 text-pink-300 border-pink-500/40',
  ミラー: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
}

const conditionLabel: Record<string, string> = {
  a: 'A（美品）',
  b: 'B（良品）',
  c: 'C（並品）',
  d: 'D（傷あり）',
  e: 'E（難あり）',
}

function parseImageUrls(card: Card): string[] {
  const urls: string[] = []
  if (card.image_url) urls.push(card.image_url)
  if (card.image_urls) {
    try {
      const extra = JSON.parse(card.image_urls) as string[]
      extra.forEach(u => { if (u && !urls.includes(u)) urls.push(u) })
    } catch { /* ignore */ }
  }
  return urls
}

export default function CardDetailClient({ id }: { id: string }) {
  const router = useRouter()
  const { isAuthenticated } = useAuthStore()
  const { addItem } = useCartStore()
  const { lang } = useLangStore()

  const [card, setCard] = useState<Card | null>(null)
  const [relatedCards, setRelatedCards] = useState<Card[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [quantity, setQuantity] = useState(1)
  const [activeImg, setActiveImg] = useState(0)
  const [isZoomed, setIsZoomed] = useState(false)
  const [addingToCart, setAddingToCart] = useState(false)

  useEffect(() => {
    const fetchCard = async () => {
      setIsLoading(true)
      try {
        const numId = parseInt(id)
        if (isNaN(numId)) { router.push('/'); return }
        const res = await cardsApi.getById(numId)
        setCard(res.data)
        if (res.data.category_id) {
          const relRes = await cardsApi.getAll({ category_id: res.data.category_id, size: 5 })
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
    if (!isAuthenticated) {
      toast({ title: t('ログインが必要です', lang), description: t('カートに追加するにはログインしてください', lang), variant: 'destructive' })
      router.push('/login')
      return
    }
    if (!card || card.stock === 0) return
    setAddingToCart(true)
    try {
      await addItem(card.id, quantity)
      toast({ title: t('カートに追加しました', lang), description: `${cardName}x${quantity}${t('をカートに追加しました', lang)}` })
    } catch {
      toast({ title: t('エラー', lang), description: t('カートへの追加に失敗しました', lang), variant: 'destructive' })
    } finally {
      setAddingToCart(false)
    }
  }

  const images = card ? parseImageUrls(card) : []
  const prevImg = useCallback(() => setActiveImg(i => (i - 1 + images.length) % images.length), [images.length])
  const nextImg = useCallback(() => setActiveImg(i => (i + 1) % images.length), [images.length])

  const cardName = useTranslation(card?.name || '')
  const categoryName = useTranslation(card?.category?.name || '')
  const description = useTranslation(card?.description || '')

  if (isLoading) {
    return (
      <div className="container py-8 animate-pulse">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="aspect-[3/4] bg-gray-800 rounded-lg" />
          <div className="space-y-4">
            <div className="h-8 bg-gray-800 rounded w-3/4" />
            <div className="h-6 bg-gray-800 rounded w-1/4" />
            <div className="h-20 bg-gray-800 rounded" />
            <div className="h-12 bg-gray-800 rounded" />
          </div>
        </div>
      </div>
    )
  }

  if (!card) return null

  const rarityClass = rarityColors[card.rarity] || rarityColors['C']

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="container py-6">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-gray-400 hover:text-white mb-6 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('戻る', lang)}
        </button>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
          {/* 画像エリア */}
          <div className="space-y-3">
            {/* メイン画像 */}
            <div
              className="relative aspect-[3/4] overflow-hidden rounded-lg border border-white/10 bg-gray-900 cursor-zoom-in"
              onClick={() => images.length > 0 && setIsZoomed(true)}
            >
              {images.length > 0 ? (
                <Image
                  src={images[activeImg]}
                  alt={cardName}
                  fill
                  className="object-cover"
                  sizes="(max-width: 768px) 100vw, 50vw"
                  unoptimized={images[activeImg].startsWith('data:')}
                />
              ) : (
                <div className="flex items-center justify-center h-full">
                  <span className="text-8xl opacity-20">🃏</span>
                </div>
              )}

              {images.length > 1 && (
                <>
                  <button onClick={(e) => { e.stopPropagation(); prevImg() }} className="absolute left-2 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/80 rounded-full p-1.5 transition-colors">
                    <ChevronLeft className="h-4 w-4 text-white" />
                  </button>
                  <button onClick={(e) => { e.stopPropagation(); nextImg() }} className="absolute right-2 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/80 rounded-full p-1.5 transition-colors">
                    <ChevronRight className="h-4 w-4 text-white" />
                  </button>
                  <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-1">
                    {images.map((_, i) => (
                      <button key={i} onClick={(e) => { e.stopPropagation(); setActiveImg(i) }}
                        className={`w-1.5 h-1.5 rounded-full transition-all ${i === activeImg ? 'bg-yellow-400 w-3' : 'bg-white/40'}`}
                      />
                    ))}
                  </div>
                </>
              )}

              <div className="absolute top-2 right-2 bg-black/50 rounded-full p-1.5">
                <ZoomIn className="h-4 w-4 text-white" />
              </div>
            </div>

            {/* サムネイル一覧 */}
            {images.length > 1 && (
              <div className="flex gap-2 overflow-x-auto pb-1">
                {images.map((url, i) => (
                  <button
                    key={i}
                    onClick={() => setActiveImg(i)}
                    className={`relative flex-shrink-0 w-14 h-18 aspect-[3/4] rounded-md overflow-hidden border-2 transition-all ${i === activeImg ? 'border-yellow-400' : 'border-white/10 hover:border-white/30'}`}
                  >
                    <Image src={url} alt={`${cardName} ${i + 1}`} fill className="object-cover" unoptimized={url.startsWith('data:')} />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 情報エリア */}
          <div className="space-y-6">
            <div>
              {card.category && (
                <p className="text-sm text-gray-500 mb-1">{categoryName}</p>
              )}
              <h1 className="text-3xl font-bold text-white mb-3">{cardName}</h1>
              <div className="flex flex-wrap gap-2">
                {card.rarity && (
                  <span className={`text-sm font-bold px-3 py-1 rounded border ${rarityClass}`}>
                    {card.rarity}
                  </span>
                )}
                {card.condition && (
                  <span className="text-sm font-medium px-3 py-1 rounded border bg-white/5 text-gray-300 border-white/20">
                    {t('状態', lang)}: {conditionLabel[card.condition] ?? card.condition.toUpperCase()}
                  </span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-4">
              <span className="text-4xl font-bold text-yellow-400">
                ¥{card.price.toLocaleString()}
              </span>
              <div className="flex items-center gap-1 text-sm text-gray-400">
                <Package className="h-4 w-4" />
                <span>{t('残り', lang)} {card.stock}{t('枚', lang)}</span>
              </div>
            </div>

            {card.description && (
              <p className="text-gray-300 leading-relaxed border-t border-white/10 pt-4">
                {description}
              </p>
            )}

            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <span className="text-sm text-gray-400">{t('数量', lang)}:</span>
                <div className="flex items-center border border-white/20 rounded-md overflow-hidden">
                  <button onClick={() => setQuantity(Math.max(1, quantity - 1))} className="px-3 py-2 text-gray-300 hover:bg-white/10 transition-colors disabled:opacity-30" disabled={quantity <= 1}>-</button>
                  <span className="px-4 py-2 text-white min-w-[3rem] text-center">{quantity}</span>
                  <button onClick={() => setQuantity(Math.min(card.stock, quantity + 1))} className="px-3 py-2 text-gray-300 hover:bg-white/10 transition-colors disabled:opacity-30" disabled={quantity >= card.stock}>+</button>
                </div>
              </div>

              <Button
                onClick={handleAddToCart}
                disabled={card.stock === 0 || addingToCart}
                className="w-full h-12 bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold text-base disabled:opacity-50"
              >
                <ShoppingCart className="h-5 w-5 mr-2" />
                {card.stock === 0 ? t('在庫なし', lang) : addingToCart ? t('追加中...', lang) : t('カートに入れる', lang)}
              </Button>
            </div>
          </div>
        </div>

        {/* 関連カード */}
        {relatedCards.length > 0 && (
          <div>
            <h2 className="text-xl font-bold text-white mb-4">{t('関連カード', lang)}</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {relatedCards.map((rc) => (
                <CardCard key={rc.id} card={rc} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ズームモーダル */}
      {isZoomed && images.length > 0 && (
        <div className="fixed inset-0 z-50 bg-black/95 flex items-center justify-center p-4" onClick={() => setIsZoomed(false)}>
          <button className="absolute top-4 right-4 text-white/70 hover:text-white" onClick={() => setIsZoomed(false)}>
            <X className="h-6 w-6" />
          </button>
          {images.length > 1 && (
            <>
              <button onClick={(e) => { e.stopPropagation(); prevImg() }} className="absolute left-4 top-1/2 -translate-y-1/2 bg-white/10 hover:bg-white/20 rounded-full p-2">
                <ChevronLeft className="h-6 w-6 text-white" />
              </button>
              <button onClick={(e) => { e.stopPropagation(); nextImg() }} className="absolute right-4 top-1/2 -translate-y-1/2 bg-white/10 hover:bg-white/20 rounded-full p-2">
                <ChevronRight className="h-6 w-6 text-white" />
              </button>
            </>
          )}
          <div className="relative max-w-lg w-full max-h-[90vh] aspect-[3/4]" onClick={e => e.stopPropagation()}>
            <Image
              src={images[activeImg]}
              alt={cardName}
              fill
              className="object-contain"
              unoptimized={images[activeImg].startsWith('data:')}
            />
          </div>
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 text-white/50 text-sm">
            {activeImg + 1} / {images.length}
          </div>
        </div>
      )}
    </div>
  )
}
