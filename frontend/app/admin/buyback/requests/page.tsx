'use client'

import Link from 'next/link'
import { ArrowLeft, Package, Store, Truck } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'

export default function BuybackRequestsHubPage() {
  const { isReady } = useAdminGuard()
  if (!isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-3xl">
        <div className="flex items-center gap-3 mb-8">
          <Link href="/admin" className="text-gray-500 hover:text-gray-900">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <Package className="h-6 w-6 text-yellow-400" />
          <h1 className="text-2xl font-bold text-gray-900">買取申請管理</h1>
        </div>
        <p className="text-gray-600 mb-8">店舗買取と郵送買取は別画面で管理します。チャネルを選択してください。</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Link
            href="/admin/buyback/mail/requests"
            className="block rounded-xl border-2 border-sky-200 bg-sky-50/50 p-6 hover:border-sky-400 transition-colors"
          >
            <Truck className="h-8 w-8 text-sky-600 mb-3" />
            <h2 className="text-lg font-semibold text-gray-900">郵送買取</h2>
            <p className="text-sm text-gray-600 mt-2">荷物受付・査定・返送・振込管理</p>
          </Link>
          <Link
            href="/admin/buyback/store/requests"
            className="block rounded-xl border-2 border-violet-200 bg-violet-50/50 p-6 hover:border-violet-400 transition-colors"
          >
            <Store className="h-8 w-8 text-violet-600 mb-3" />
            <h2 className="text-lg font-semibold text-gray-900">店舗買取</h2>
            <p className="text-sm text-gray-600 mt-2">来店・査定・店頭支払い管理</p>
          </Link>
        </div>
      </div>
    </div>
  )
}
