'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Package, ChevronDown, ChevronUp } from 'lucide-react'
import { useBackendAuth } from '@/hooks/useBackendAuth'
import { ordersApi } from '@/lib/api'
import { Order } from '@/lib/types'
import { usePrice } from '@/lib/format'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { useTranslation } from '@/hooks/useTranslation'
import { OrderReceiptDialog } from '@/components/orders/OrderReceiptDialog'
import { buildTrackingUrl } from '@/lib/tracking'

const statusLabels: Record<string, string> = {
  pending: '処理中',
  processing: '準備中',
  shipped: '発送済み',
  delivered: '配達完了',
  cancelled: 'キャンセル',
  unshipped: '未発送',
  preparing: '準備中',
}

const paymentStatusLabels: Record<string, string> = {
  awaiting_payment: '入金待ち',
  pending: '未決済',
  paid: '支払い済み',
  expired: '期限切れ',
  cancelled: 'キャンセル',
}

const paymentMethodLabels: Record<string, string> = {
  stripe_card: 'クレジットカード',
  stripe_bank_transfer: '銀行振込（Stripe）',
  bank_transfer: '銀行振込',
  cod: '代金引換',
}

const statusColors: Record<string, string> = {
  pending: 'text-yellow-400',
  processing: 'text-blue-400',
  shipped: 'text-purple-400',
  delivered: 'text-green-400',
  cancelled: 'text-red-400',
  unshipped: 'text-gray-400',
  preparing: 'text-blue-400',
}

export default function OrdersPage() {
  const router = useRouter()
  const { isLoggedIn, isReady, requireAuth, user } = useBackendAuth()
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
    if (!isMounted || !isReady) return

    if (!isLoggedIn) {
      router.push('/sign-in')
      return
    }

    void requireAuth().then((token) => {
      if (!token) {
        router.push('/sign-in')
        return
      }
      ordersApi.getAll().then((res) => {
        setOrders(res.data || [])
      }).catch(() => {}).finally(() => setIsLoading(false))
    })
  }, [isMounted, isReady, isLoggedIn, router, requireAuth])

  if (!isMounted || !isReady || !isLoggedIn) return null

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
            const displayStatus = order.shipping_status || order.status
            const statusLabel = statusLabels[displayStatus] || displayStatus
            const statusColor = statusColors[displayStatus] || 'text-gray-400'
            const isExpanded = expandedId === order.id

            return (
              <div key={order.id} className="bg-gray-50 rounded-lg border border-gray-200">
                <button
                  onClick={() => setExpandedId(isExpanded ? null : order.id)}
                  className="w-full flex items-center justify-between p-4 text-left"
                >
                  <div className="flex items-center gap-4">
                    <div>
                      <p className="text-gray-900 font-medium">
                        {order.order_number
                          ? `${t('注文番号', lang)}: ${order.order_number}`
                          : `${t('注文番号', lang)} #${order.id}`}
                      </p>
                      {order.order_number && (
                        <p className="text-gray-400 text-xs">ID #{order.id}</p>
                      )}
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
                      <div className="text-sm space-y-1">
                        <div>
                          <span className="text-gray-500">{t('支払い方法', lang)}: </span>
                          <span className="text-gray-600">
                            {t(paymentMethodLabels[order.payment_method || ''] || order.payment_method || '-', lang)}
                          </span>
                          <span className="text-gray-400 mx-2">/</span>
                          <span className="text-gray-600">
                            {t(paymentStatusLabels[order.payment_status] || order.payment_status, lang)}
                          </span>
                        </div>
                        {order.payment_status === 'awaiting_payment' && order.payment_deadline && (
                          <p className="text-amber-600 text-xs">
                            {t('お支払い期限', lang)}: {new Date(order.payment_deadline).toLocaleString(lang === 'ja' ? 'ja-JP' : 'en-US')}
                          </p>
                        )}
                        {order.stock_reserved && order.payment_status === 'awaiting_payment' && (
                          <p className="text-orange-600/80 text-xs">{t('商品は取り置き中です。期限内にお振込みください。', lang)}</p>
                        )}
                        {order.tracking_number && (() => {
                          const trackingUrl = buildTrackingUrl(
                            order.tracking_number,
                            order.shipping_method,
                            order.shipping_carrier
                          )
                          return (
                            <p className="text-purple-600 text-xs font-mono">
                              {lang === 'ja' ? '追跡番号' : 'Tracking'}:{' '}
                              {trackingUrl ? (
                                <a
                                  href={trackingUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="underline hover:text-purple-800"
                                >
                                  {order.tracking_number}
                                </a>
                              ) : (
                                order.tracking_number
                              )}
                            </p>
                          )
                        })()}
                      </div>
                    )}
                    {order.payment_status === 'paid' && (user?.name || user?.email) && (
                      <div className="border-t border-gray-200 pt-3">
                        <OrderReceiptDialog
                          order={order}
                          buyerName={user.name || user.email.split('@')[0]}
                        />
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
