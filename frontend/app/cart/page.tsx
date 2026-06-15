'use client'

import { useState, useEffect } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Trash2, Plus, Minus, ShoppingBag, ArrowRight } from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { useCartStore } from '@/store/cart'
import { toast } from '@/lib/use-toast'
import { Button } from '@/components/ui/button'

export default function CartPage() {
  const router = useRouter()
  const { isAuthenticated, isLoading: isAuthLoading } = useAuthStore()
  const { items, total, isLoading, fetchCart, updateItem, removeItem } = useCartStore()
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  useEffect(() => {
    if (!isMounted || isAuthLoading) return

    if (!isAuthenticated) {
      router.push('/login')
      return
    }
    fetchCart()
  }, [isMounted, isAuthLoading, isAuthenticated, router, fetchCart])

  const handleUpdateQuantity = async (itemId: number, newQty: number) => {
    if (newQty < 1) return
    try {
      await updateItem(itemId, newQty)
    } catch {
      toast({ title: 'エラー', description: '数量の更新に失敗しました', variant: 'destructive' })
    }
  }

  const handleRemove = async (itemId: number, cardName: string) => {
    try {
      await removeItem(itemId)
      toast({ title: '削除しました', description: `${cardName}をカートから削除しました` })
    } catch {
      toast({ title: 'エラー', description: '削除に失敗しました', variant: 'destructive' })
    }
  }

  if (!isMounted || isAuthLoading || !isAuthenticated) return null

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-gray-400 animate-pulse">読み込み中...</div>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center gap-4">
        <ShoppingBag className="h-16 w-16 text-gray-700" />
        <h2 className="text-xl font-bold text-white">カートは空です</h2>
        <p className="text-gray-400 text-sm">カードを選んでカートに追加しましょう</p>
        <Link href="/">
          <Button className="bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold mt-2">
            カードを見る
          </Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="container py-8 max-w-4xl">
        <h1 className="text-2xl font-bold text-white mb-6">ショッピングカート</h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Items */}
          <div className="lg:col-span-2 space-y-3">
            {items.map((item) => (
              <div
                key={item.id}
                className="flex gap-4 bg-gray-900 rounded-lg border border-white/10 p-4"
              >
                {/* Image */}
                <div className="relative w-16 h-20 flex-shrink-0 overflow-hidden rounded bg-gray-800">
                  {item.card?.image_url ? (
                    <Image
                      src={item.card.image_url}
                      alt={item.card.name}
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
                    className="text-white font-medium hover:text-yellow-400 transition-colors truncate block"
                  >
                    {item.card?.name || '不明なカード'}
                  </Link>
                  <p className="text-xs text-gray-500 mt-0.5">{item.card?.rarity}</p>
                  <p className="text-yellow-400 font-bold mt-1">
                    ¥{((item.card?.price || 0) * item.quantity).toLocaleString()}
                  </p>
                </div>

                {/* Controls */}
                <div className="flex flex-col items-end gap-2">
                  <button
                    onClick={() => handleRemove(item.id, item.card?.name || '')}
                    className="text-gray-500 hover:text-red-400 transition-colors"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                  <div className="flex items-center border border-white/20 rounded overflow-hidden">
                    <button
                      onClick={() => handleUpdateQuantity(item.id, item.quantity - 1)}
                      disabled={item.quantity <= 1}
                      className="px-2 py-1 text-gray-300 hover:bg-white/10 disabled:opacity-30 transition-colors"
                    >
                      <Minus className="h-3 w-3" />
                    </button>
                    <span className="px-3 py-1 text-white text-sm min-w-[2.5rem] text-center">
                      {item.quantity}
                    </span>
                    <button
                      onClick={() => handleUpdateQuantity(item.id, item.quantity + 1)}
                      disabled={item.card?.stock !== undefined && item.quantity >= item.card.stock}
                      className="px-2 py-1 text-gray-300 hover:bg-white/10 disabled:opacity-30 transition-colors"
                    >
                      <Plus className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Summary */}
          <div className="lg:col-span-1">
            <div className="bg-gray-900 rounded-lg border border-white/10 p-5 sticky top-24">
              <h2 className="text-white font-bold text-lg mb-4">注文サマリー</h2>
              <div className="space-y-2 mb-4">
                <div className="flex justify-between text-sm text-gray-400">
                  <span>商品数</span>
                  <span>{items.reduce((sum, i) => sum + i.quantity, 0)}点</span>
                </div>
                <div className="flex justify-between text-sm text-gray-400">
                  <span>小計</span>
                  <span>¥{total.toLocaleString()}</span>
                </div>
                <div className="border-t border-white/10 pt-2 flex justify-between font-bold text-white">
                  <span>合計</span>
                  <span className="text-yellow-400">¥{total.toLocaleString()}</span>
                </div>
              </div>
              <Button
                onClick={() => router.push('/checkout')}
                className="w-full bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold h-11"
              >
                購入手続きへ
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
