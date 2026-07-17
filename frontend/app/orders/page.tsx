'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Package, ChevronDown, ChevronUp } from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { ordersApi } from '@/lib/api'
import { Order } from '@/lib/types'
import { usePrice } from '@/lib/format'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { useTranslation } from '@/hooks/useTranslation'

const statusLabels: Record<string, string> = {
  pending: '処理中',
  processing: '準備中',
  shipped: '発送済み',
  delivered: '配達完了',
  cancelled: 'キャンセル',
}

const paymentStatusLabels: Record<string, string> = {
  awaiting_payment: '決済待ち',
  pending: '未決済',
  paid: '決済済み',
}

const statusColors: Record<string, string> = {
  pending: 'text-yellow-400',
  processing: 'text-blue-400',
  shipped: 'text-purple-400',
  delivered: 'text-green-400',
  cancelled: 'text-red-400',
}

export default function OrdersPage() {
  const router = useRouter()
  const { isAuthenticated, isLoading: isAuthLoading } = useAuthStore()
  const { formatPrice } = usePrice()
  const { lang } = useLangStore()
  const [orders, setOrders] = useState<Order[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<number | null>(null)
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
    ordersApi.getAll().then((res) => {
      setOrders(res.data || [])
    }).catch(() => {}).finally(() => setIsLoading(false))
  }, [isMounted, isAuthLoading, isAuthenticated, router])

  if (!isMounted || isAuthLoading || !isAuthenticated) return null

  if (isLoading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-gray-400 animate-pulse">{t('読み込み中...', lang)}</div>
      </div>
    )
  }

  if (orders.length === 0) {
    return (
      <div className="min-h-screen bg-white flex flex-col items-center justify-center gap-4">
        <Package className="h-16 w-16 text-gray-700" />
        <h2 className="text-xl font-bold text-gray-900">{t('注文履歴はありません', lang)}</h2>
        <p className="text-gray-400 text-sm">{t('まだ注文がありません', lang)}</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-3xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">{t('注文履歴', lang)}</h1>

        <div className="space-y-3">
          {orders.map((order) => {
            const statusLabel = statusLabels[order.status] || order.status
            const statusColor = statusColors[order.status] || 'text-gray-400'
            const isExpanded = expandedId === order.id

            return (
              <div key={order.id} className="bg-gray-50 rounded-lg border border-gray-200">
                <button
                  onClick={() => setExpandedId(isExpanded ? null : order.id)}
                  className="w-full flex items-center justify-between p-4 text-left"
                >
                  <div className="flex items-center gap-4">
                    <div>
                      <p className="text-gray-900 font-medium">{t('注文番号', lang)} #{order.id}</p>
                      <p className="text-gray-500 text-sm">
                        {new Date(order.created_at).toLocaleDateString(lang === 'ja' ? 'ja-JP' : 'en-US')}
                      </p>
                    </div>
                    <span className={`text-sm font-medium ${statusColor}`}>{t(statusLabel, lang)}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-yellow-400 font-bold">{formatPrice(order.total_amount)}</span>
                    {isExpanded ? (
                      <ChevronUp className="h-4 w-4 text-gray-400" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-gray-400" />
                    )}
                  </div>
                </button>

                {isExpanded && (
                  <div className="border-t border-gray-200 p-4 space-y-3">
                    <OrderItemsList items={order.items} formatPrice={formatPrice} lang={lang} />
                    {order.shipping_address && (
                      <div className="border-t border-gray-200 pt-3 text-sm">
                        <span className="text-gray-500">{t('配送先', lang)}: </span>
                        <span className="text-gray-600">{order.shipping_address}</span>
                      </div>
                    )}
                    {order.payment_status && (
                      <div className="text-sm">
                        <span className="text-gray-500">{t('支払い方法', lang)}: </span>
                        <span className="text-gray-600">{order.payment_method || '-'}</span>
                        <span className="text-gray-400 mx-2">/</span>
                        <span className="text-gray-600">
                          {t(paymentStatusLabels[order.payment_status] || order.payment_status, lang)}
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function OrderItemsList({ items, formatPrice, lang }: any) {
  return (
    <>
      {items?.map((item: any) => (
        <OrderItemRow key={item.id} item={item} formatPrice={formatPrice} lang={lang} />
      ))}
    </>
  )
}

function OrderItemRow({ item, formatPrice, lang }: any) {
  const translatedCardName = useTranslation(item.card?.name)
  const cardName = (lang === 'en' && item.card?.name_en) ? item.card.name_en : translatedCardName
  return (
    <div className="flex justify-between items-center text-sm">
      <span className="text-gray-600">{cardName || `${t('カード', lang)} #${item.card_id}`}</span>
      <span className="text-gray-400">
        {formatPrice(item.unit_price || 0)} × {item.quantity}
      </span>
    </div>
  )
}
