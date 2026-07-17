'use client'

import { Suspense } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { XCircle } from 'lucide-react'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { Button } from '@/components/ui/button'

export default function CheckoutCancelPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-white" />}>
      <CheckoutCancelContent />
    </Suspense>
  )
}

function CheckoutCancelContent() {
  const searchParams = useSearchParams()
  const orderId = searchParams.get('order_id')
  const { lang } = useLangStore()

  return (
    <div className="min-h-screen bg-white flex items-center justify-center p-6">
      <div className="max-w-md w-full text-center space-y-6">
        <XCircle className="h-16 w-16 text-gray-400 mx-auto" />
        <h1 className="text-2xl font-bold text-gray-900">{t('決済がキャンセルされました', lang)}</h1>
        <p className="text-gray-600 text-sm leading-relaxed">
          {t('決済は完了していません。カートの内容はそのままです。', lang)}
          {orderId ? ` (${t('注文番号', lang)}: #${orderId})` : ''}
        </p>
        <div className="flex flex-col gap-3 pt-2">
          <Link href="/checkout">
            <Button className="w-full bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold">
              {t('チェックアウトに戻る', lang)}
            </Button>
          </Link>
          <Link href="/cart">
            <Button variant="outline" className="w-full">
              {t('カートを見る', lang)}
            </Button>
          </Link>
        </div>
      </div>
    </div>
  )
}
