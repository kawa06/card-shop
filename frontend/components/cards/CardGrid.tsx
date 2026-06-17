'use client'

import CardCard from './CardCard'
import { Card } from '@/lib/types'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'

interface CardGridProps {
  cards: Card[]
  isLoading?: boolean
}

function CardSkeleton() {
  return (
    <div className="rounded-lg border border-white/10 bg-gray-900 overflow-hidden animate-pulse">
      <div className="aspect-[3/4] bg-gray-800" />
      <div className="p-3 space-y-2">
        <div className="h-4 bg-gray-800 rounded w-3/4" />
        <div className="h-4 bg-gray-800 rounded w-1/2" />
        <div className="h-8 bg-gray-800 rounded mt-2" />
      </div>
    </div>
  )
}

export default function CardGrid({ cards, isLoading }: CardGridProps) {
  const { lang } = useLangStore()

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {Array.from({ length: 10 }).map((_, i) => (
          <CardSkeleton key={i} />
        ))}
      </div>
    )
  }

  if (cards.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-500">
        <span className="text-6xl mb-4">🃏</span>
        <p className="text-lg font-medium">{t('カードが見つかりませんでした', lang)}</p>
        <p className="text-sm mt-1">{t('検索条件を変更してみてください', lang)}</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
      {cards.map((card) => (
        <CardCard key={card.id} card={card} />
      ))}
    </div>
  )
}
