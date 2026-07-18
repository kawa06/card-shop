'use client'

import Image from 'next/image'
import Link from 'next/link'
import { ShoppingCart } from 'lucide-react'
import { Card } from '@/lib/types'
import { useBackendAuth } from '@/hooks/useBackendAuth'
import { useCartStore } from '@/store/cart'
import { useLangStore } from '@/store/lang'
import { toast } from '@/lib/use-toast'
import { t } from '@/lib/i18n'
import { useTranslation } from '@/hooks/useTranslation'
import { usePrice } from '@/lib/format'
import { Button } from '@/components/ui/button'
import FavoriteButton from '@/components/cards/FavoriteButton'

interface CardCardProps {
  card: Card
}

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

const conditionLabel: Record<string, string> = {
  a: 'A',
  b: 'B',
  c: 'C',
  d: 'D',
  e: 'E',
}

export default function CardCard({ card }: CardCardProps) {
  const { isLoggedIn, isReady, requireAuth } = useBackendAuth()
  const { addItem } = useCartStore()
  const { lang } = useLangStore()
  const { formatPrice } = usePrice()
  const translatedCardName = useTranslation(card.name)
  const cardName = (lang === 'en' && card.name_en) ? card.name_en : translatedCardName
  const categoryName = useTranslation(card.category?.name || '')

  const handleAddToCart = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!isReady) return
    if (!isLoggedIn) {
      toast({
        title: t('ログインが必要です', lang),
        description: t('カートに追加するにはログインしてください', lang),
        variant: 'destructive',
      })
      return
    }
    if (card.stock === 0) return
    try {
      const token = await requireAuth()
      if (!token) {
        toast({
          title: t('ログインが必要です', lang),
          description: t('カートに追加するにはログインしてください', lang),
          variant: 'destructive',
        })
        return
      }
      await addItem(card.id, 1)
      toast({
        title: t('カートに追加しました', lang),
        description: `${cardName}${t('をカートに追加しました', lang)}`,
      })
    } catch {
      toast({
        title: t('エラー', lang),
        description: t('カートへの追加に失敗しました', lang),
        variant: 'destructive',
      })
    }
  }

  const rarityClass = rarityColors[card.rarity] || rarityColors['C']

  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-gray-50 transition-colors duration-300 hover:border-yellow-400/30 hover:shadow-lg hover:shadow-yellow-400/5">
      <Link href={`/cards/${card.id}`} className="block">
        <div className="relative aspect-[3/4] overflow-hidden bg-white">
          {card.image_url ? (
            <Image
              src={card.image_url}
              alt={cardName}
              fill
              className="object-cover"
              sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw"
              unoptimized={card.image_url.startsWith('data:')}
            />
          ) : (
            <div className="flex items-center justify-center h-full">
              <span className="text-4xl opacity-20">🃏</span>
            </div>
          )}
          <div className="absolute top-2 right-2 z-10 flex flex-col items-end gap-1.5">
            <FavoriteButton cardId={card.id} size="sm" />
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${rarityClass}`}>
              {card.rarity}
            </span>
          </div>
          {card.condition && (
            <div className="absolute top-2 left-2 z-10">
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded border bg-black/60 text-white border-gray-300 backdrop-blur-sm">
                {t('状態', lang)} {conditionLabel[card.condition] ?? card.condition.toUpperCase()}
              </span>
            </div>
          )}
          {card.stock === 0 && (
            <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
              <span className="text-white font-bold text-sm bg-red-600/80 px-3 py-1 rounded">
                {t('売り切れ', lang)}
              </span>
            </div>
          )}
        </div>

        <div className="p-3">
          <h3 className="text-gray-900 font-medium text-sm truncate mb-1">{cardName}</h3>
          <div className="flex items-center justify-between">
            <span className="text-yellow-400 font-bold">
              {formatPrice(card.price)}
            </span>
            <span className="text-xs text-gray-500">
              {t('残り', lang)} {card.stock}{t('枚', lang)}
            </span>
          </div>
          {card.category && (
            <span className="text-xs text-gray-500 mt-1 block">{categoryName}</span>
          )}
          {card.pack && (
            <span className="text-xs text-sky-600 mt-0.5 block truncate">{card.pack.name}</span>
          )}
        </div>
      </Link>

      <div className="px-3 pb-3">
        <Button
          onClick={handleAddToCart}
          disabled={card.stock === 0}
          size="sm"
          className="w-full bg-yellow-400/10 text-yellow-400 border border-yellow-400/20 hover:bg-yellow-400 hover:text-gray-950 transition-colors disabled:opacity-50"
        >
          <ShoppingCart className="h-4 w-4 shrink-0 mr-2" />
          {card.stock === 0 ? t('在庫なし', lang) : t('カートに追加', lang)}
        </Button>
      </div>
    </div>
  )
}
