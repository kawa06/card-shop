'use client'

import { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { CheckCircle2, Landmark, Loader2 } from 'lucide-react'
import { paymentsApi } from '@/lib/api'
import { useBackendAuth } from '@/hooks/useBackendAuth'
import { useCartStore } from '@/store/cart'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { Button } from '@/components/ui/button'

export default function CheckoutSuccessPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-white flex items-center justify-center">
        <Loader2 className="h-12 w-12 text-yellow-400 animate-spin" />
      </div>
    }>
      <CheckoutSuccessContent />
    </Suspense>
  )
}

function CheckoutSuccessContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const sessionId = searchParams.get('session_id')
  const { clearCart, fetchCart } = useCartStore()
  const { isLoggedIn, isReady, requireAuth } = useBackendAuth()
  const { lang } = useLangStore()
  const [orderId, setOrderId] = useState<number | null>(null)
  const [pendingBankTransfer, setPendingBankTransfer] = useState(false)
  const [error, setError] = useState<string | null>(null)
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
    if (!sessionId) {
      setError(lang === 'ja' ? '決済セッションが見つかりません' : 'Payment session not found')
      return
    }

    void requireAuth().then((token) => {
      if (!token) {
        router.push('/sign-in')
        return
      }

      paymentsApi
        .confirmStripeCheckout(sessionId)
        .then((res) => {
          setOrderId(res.data.order.id)
          setPendingBankTransfer(Boolean(res.data.pending_bank_transfer))
          clearCart()
          fetchCart()
        })
        .catch((err) => {
          const message =
            err?.response?.data?.detail ||
            (lang === 'ja' ? '決済の確認に失敗しました' : 'Failed to confirm payment')
          setError(typeof message === 'string' ? message : JSON.stringify(message))
        })
    })
  }, [isMounted, isReady, isLoggedIn, sessionId, router, clearCart, fetchCart, lang, requireAuth])

  if (!isMounted || !isReady || !isLoggedIn) return null

  return (
    <div className="min-h-screen bg-white flex items-center justify-center p-6">
      <div className="max-w-md w-full text-center space-y-6">
        {!orderId && !error && (
          <>
            <Loader2 className="h-12 w-12 text-yellow-400 animate-spin mx-auto" />
            <p className="text-gray-600">{t('決済を確認しています...', lang)}</p>
          </>
        )}

        {orderId && pendingBankTransfer && (
          <>
            <Landmark className="h-16 w-16 text-yellow-500 mx-auto" />
            <h1 className="text-2xl font-bold text-gray-900">
              {lang === 'ja' ? '銀行振込のお手続きを受け付けました' : 'Bank transfer instructions received'}
            </h1>
            <p className="text-gray-600 text-sm leading-relaxed">
              {t('注文番号', lang)}: #{orderId}
            </p>
            <p className="text-gray-600 text-sm leading-relaxed">
              {lang === 'ja'
                ? 'Stripeの画面で表示された振込先へ、指定金額をお振り込みください。入金確認後に発送します。'
                : 'Please transfer the exact amount to the bank account shown on Stripe. We ship after payment is confirmed.'}
            </p>
            <div className="flex flex-col gap-3 pt-4">
              <Link href="/orders">
                <Button className="w-full bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold">
                  {t('注文履歴を見る', lang)}
                </Button>
              </Link>
            </div>
          </>
        )}

        {orderId && !pendingBankTransfer && (
          <>
            <CheckCircle2 className="h-16 w-16 text-green-500 mx-auto" />
            <h1 className="text-2xl font-bold text-gray-900">{t('決済が完了しました', lang)}</h1>
            <p className="text-gray-600">
              {t('注文番号', lang)}: #{orderId}
            </p>
            <div className="flex flex-col gap-3 pt-4">
              <Link href="/orders">
                <Button className="w-full bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold">
                  {t('注文履歴を見る', lang)}
                </Button>
              </Link>
              <Link href="/">
                <Button variant="outline" className="w-full">
                  {t('ショップを見る', lang)}
                </Button>
              </Link>
            </div>
          </>
        )}

        {error && (
          <>
            <h1 className="text-xl font-bold text-red-600">{t('エラー', lang)}</h1>
            <p className="text-gray-600 text-sm">{error}</p>
            <Link href="/checkout">
              <Button className="mt-4 bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold">
                {t('チェックアウトに戻る', lang)}
              </Button>
            </Link>
          </>
        )}
      </div>
    </div>
  )
}
