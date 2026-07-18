'use client'

import { useState, useEffect } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Trash2, Plus, Minus, ShoppingBag, ArrowRight } from 'lucide-react'
import { useBackendAuth } from '@/hooks/useBackendAuth'
import { useCartStore } from '@/store/cart'
import { usePrice } from '@/lib/format'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { useTranslation } from '@/hooks/useTranslation'
import { toast } from '@/lib/use-toast'
import { Button } from '@/components/ui/button'

export default function CartPage() {
  const router = useRouter()
  const { isLoggedIn, isReady, requireAuth } = useBackendAuth()
  const { items, total, isLoading, fetchCart, updateItem, removeItem } = useCartStore()
  const { formatPrice } = usePrice()
  const { lang } = useLangStore()
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

    void requireAuth().then((token) => {
      if (token) fetchCart()
    })
  }, [isMounted, isReady, isLoggedIn, router, fetchCart, requireAuth])

  const handleUpdateQuantity = async (itemId: number, newQty: number) => {
    if (newQty < 1) return
    try {
      await updateItem(itemId, newQty)
    } catch {
      toast({ title: t('エラー', lang), description: lang === 'ja' ? '数量の更新に失敗しました' : 'Failed to update quantity', variant: 'destructive' })
    }
  }

  const handleRemove = async (itemId: number, cardName: string) => {
    try {
      await removeItem(itemId)
      toast({ title: t('削除しました', lang), description: lang === 'ja' ? `${cardName}をカートから削除しました` : `Removed ${cardName} from cart` })
    } catch {
      toast({ title: t('エラー', lang), description: lang === 'ja' ? '削除に失敗しました' : 'Failed to remove item', variant: 'destructive' })
    }
  }

  if (!isMounted || !isReady || !isLoggedIn) return null

  if (isLoading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-gray-400 animate-pulse">{t('読み込み中...', lang)}</div>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="min-h-screen bg-white flex flex-col items-center justify-center gap-4">
        <ShoppingBag className="h-16 w-16 text-gray-700" />
        <h2 className="text-xl font-bold text-gray-900">{t('カートは空です', lang)}</h2>
        <p className="text-gray-400 text-sm">{lang === 'ja' ? 'カードを選んでカートに追加しましょう' : 'Let\'s choose some cards and add them to your cart'}</p>
        <Link href="/">
          <Button className="bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold mt-2">
            {t('カードを見る', lang)}
          </Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-4xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">{t('ショッピングカート', lang)}</h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Items */}
          <div className="lg:col-span-2 space-y-3">
            {items.map((item) => (
              <CartItemRow key={item.id} item={item} formatPrice={formatPrice} handleRemove={handleRemove} handleUpdateQuantity={handleUpdateQuantity} lang={lang} />
            ))}
          </div>

          {/* Summary */}
          <div className="lg:col-span-1">
            <div className="bg-gray-50 rounded-lg border border-gray-200 p-5 sticky top-24">
              <h2 className="text-gray-900 font-bold text-lg mb-4">{t('注文サマリー', lang)}</h2>
              <div className="space-y-2 mb-4">
                <div className="flex justify-between text-sm text-gray-400">
                  <span>{t('商品数', lang)}</span>
                  <span>{items.reduce((sum, i) => sum + i.quantity, 0)}{t('点', lang)}</span>
                </div>
                <div className="flex justify-between text-sm text-gray-400">
                  <span>{t('小計', lang)}</span>
                  <span>{formatPrice(total)}</span>
                </div>
                <div className="border-t border-gray-200 pt-2 flex justify-between font-bold text-gray-900">
                  <span>{t('合計', lang)}</span>
                  <span className="text-yellow-400">{formatPrice(total)}</span>
                </div>
              </div>
              <Button
                onClick={() => router.push('/checkout')}
                className="w-full bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold h-11"
              >
                {t('購入手続きへ', lang)}
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function CartItemRow({ item, formatPrice, handleRemove, handleUpdateQuantity, lang }: any) {
  const translatedCardName = useTranslation(item.card?.name)
  const cardName = (lang === 'en' && item.card?.name_en) ? item.card.name_en : translatedCardName
  return (
    <div
      className="flex gap-4 bg-gray-50 rounded-lg border border-gray-200 p-4"
    >
      {/* Image */}
      <div className="relative w-16 h-20 flex-shrink-0 overflow-hidden rounded bg-white">
        {item.card?.image_url ? (
          <Image
            src={item.card.image_url}
            alt={cardName}
            fill
            className="object-cover"
          />
        ) : (
          <div className="flex items-center justify-center h-full text-2xl">🃏</div>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <Link
          href={`/cards/${item.card?.id}`}
          className="text-gray-900 font-medium hover:text-yellow-400 transition-colors truncate block"
        >
          {cardName || t('不明なカード', lang)}
        </Link>
        <p className="text-xs text-gray-500 mt-0.5">{item.card?.rarity}</p>
        <p className="text-yellow-400 font-bold mt-1">
          {formatPrice((item.card?.price || 0) * item.quantity)}
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-col items-end gap-2">
        <button
          onClick={() => handleRemove(item.id, cardName || '')}
          className="text-gray-500 hover:text-red-400 transition-colors"
        >
          <Trash2 className="h-4 w-4" />
        </button>
        <div className="flex items-center border border-gray-300 rounded overflow-hidden">
          <button
            onClick={() => handleUpdateQuantity(item.id, item.quantity - 1)}
            disabled={item.quantity <= 1}
            className="px-2 py-1 text-gray-600 hover:bg-gray-100 disabled:opacity-30 transition-colors"
          >
            <Minus className="h-3 w-3" />
          </button>
          <span className="px-3 py-1 text-gray-900 text-sm min-w-[2.5rem] text-center">
            {item.quantity}
          </span>
          <button
            onClick={() => handleUpdateQuantity(item.id, item.quantity + 1)}
            disabled={item.card?.stock !== undefined && item.quantity >= item.card.stock}
            className="px-2 py-1 text-gray-600 hover:bg-gray-100 disabled:opacity-30 transition-colors"
          >
            <Plus className="h-3 w-3" />
          </button>
        </div>
      </div>
    </div>
  )
}
