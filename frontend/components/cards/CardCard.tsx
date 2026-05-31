'use client'

import Image from 'next/image'
import Link from 'next/link'
import { ShoppingCart } from 'lucide-react'
import { Card } from '@/lib/types'
import { useAuthStore } from '@/store/auth'
import { useCartStore } from '@/store/cart'
import { toast } from '@/lib/use-toast'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

interface CardCardProps {
  card: Card
}

const rarityColors: Record<string, string> = {
  UR: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40',
  SR: 'bg-purple-500/20 text-purple-300 border-purple-500/40',
  R: 'bg-blue-500/20 text-blue-300 border-blue-500/40',
  N: 'bg-gray-500/20 text-gray-300 border-gray-500/40',
  SSR: 'bg-pink-500/20 text-pink-300 border-pink-500/40',
}

export default function CardCard({ card }: CardCardProps) {
  const { isAuthenticated } = useAuthStore()
  const { addItem } = useCartStore()

  const handleAddToCart = async (e: React.MouseEvent) => {
    e.preventDefault()
    if (!isAuthenticated) {
      toast({
        title: 'ログインが必要です',
        description: 'カートに追加するにはログインしてください',
        variant: 'destructive',
      })
      return
    }
    if (card.stock === 0) return
    try {
      await addItem(card.id, 1)
      toast({
        title: 'カートに追加しました',
        description: `${card.name}をカートに追加しました`,
      })
    } catch {
      toast({
        title: 'エラー',
        description: 'カートへの追加に失敗しました',
        variant: 'destructive',
      })
    }
  }

  const rarityClass = rarityColors[card.rarity] || rarityColors['N']

  return (
    <Link href={`/cards/${card.id}`} className="group block">
      <div className="relative overflow-hidden rounded-lg border border-white/10 bg-gray-900 transition-all duration-300 hover:border-yellow-400/30 hover:shadow-lg hover:shadow-yellow-400/5 hover:-translate-y-1">
        {/* Card Image */}
        <div className="relative aspect-[3/4] overflow-hidden bg-gray-800">
          {card.image_url ? (
            <Image
              src={card.image_url}
              alt={card.name}
              fill
              className="object-cover transition-transform duration-300 group-hover:scale-105"
              sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw"
            />
          ) : (
            <div className="flex items-center justify-center h-full">
              <span className="text-4xl opacity-20">🃏</span>
            </div>
          )}
          {/* Rarity Badge */}
          <div className="absolute top-2 right-2">
            <span className={`text-xs font-bold px-2 py-0.5 rounded border ${rarityClass}`}>
              {card.rarity}
            </span>
          </div>
          {/* Out of stock overlay */}
          {card.stock === 0 && (
            <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
              <span className="text-white font-bold text-sm bg-red-600/80 px-3 py-1 rounded">
                売り切れ
              </span>
            </div>
          )}
        </div>

        {/* Card Info */}
        <div className="p-3">
          <h3 className="text-white font-medium text-sm truncate mb-1">{card.name}</h3>
          <div className="flex items-center justify-between">
            <span className="text-yellow-400 font-bold">
              ¥{card.price.toLocaleString()}
            </span>
            <span className="text-xs text-gray-500">
              残り {card.stock}枚
            </span>
          </div>
          {card.category && (
            <span className="text-xs text-gray-500 mt-1 block">{card.category.name}</span>
          )}
        </div>

        {/* Add to cart button */}
        <div className="px-3 pb-3">
          <Button
            onClick={handleAddToCart}
            disabled={card.stock === 0}
            size="sm"
            className="w-full bg-yellow-400/10 text-yellow-400 border border-yellow-400/20 hover:bg-yellow-400 hover:text-gray-950 transition-colors disabled:opacity-50"
          >
            <ShoppingCart className="h-3 w-3 mr-1" />
            {card.stock === 0 ? '在庫なし' : 'カートに追加'}
          </Button>
        </div>
      </div>
    </Link>
  )
}
