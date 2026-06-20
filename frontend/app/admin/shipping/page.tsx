'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowLeft, RefreshCw, ExternalLink, Shield, Globe, Truck } from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { shippingApi } from '@/lib/api'
import { ShippingRate } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { toast } from '@/lib/use-toast'
import { usePrice } from '@/lib/format'

export default function AdminShippingPage() {
  const router = useRouter()
  const { isAuthenticated, user, isLoading: isAuthLoading } = useAuthStore()
  const { lang } = useLangStore()
  const { formatPrice } = usePrice()
  const [rates, setRates] = useState<ShippingRate[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const fetchRates = async () => {
    setIsLoading(true)
    try {
      const res = await shippingApi.getRates()
      setRates(res.data)
    } catch (err) {
      toast({ title: 'Error', description: 'Failed to fetch shipping rates', variant: 'destructive' })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!isMounted || isAuthLoading) return
    if (!isAuthenticated || (user && !user.is_admin)) {
      router.push('/')
      return
    }
    fetchRates()
  }, [isMounted, isAuthLoading, isAuthenticated, user, router])

  const handleRefresh = async () => {
    setIsRefreshing(true)
    try {
      await shippingApi.refreshRates()
      toast({ title: 'Success', description: 'Shipping rates updated from official sources' })
      await fetchRates()
    } catch (err) {
      toast({ title: 'Error', description: 'Failed to refresh rates', variant: 'destructive' })
    } finally {
      setIsRefreshing(false)
    }
  }

  if (!isMounted || !isAuthenticated || (user && !user.is_admin)) return null

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="container py-8 max-w-5xl">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push('/admin')}
              className="p-2 rounded-full hover:bg-white/5 text-gray-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Truck className="h-6 w-6 text-orange-400" />
              {t('送料管理', lang)}
            </h1>
          </div>
          <Button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="bg-orange-500 hover:bg-orange-600 text-white font-bold flex items-center gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            {lang === 'ja' ? '最新料金を取得' : 'Refresh Rates'}
          </Button>
        </div>

        {isLoading ? (
          <div className="grid gap-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-32 bg-gray-900 rounded-xl border border-white/5 animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid gap-4">
            {rates.map((rate) => (
              <div key={rate.method_code} className="bg-gray-900 rounded-xl border border-white/10 p-6">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <h2 className="text-lg font-bold text-white">
                        {lang === 'ja' ? rate.name_ja : rate.name_en}
                      </h2>
                      <span className="text-[10px] bg-gray-800 text-gray-400 px-2 py-0.5 rounded border border-white/5">
                        {rate.method_code}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-2 mb-3">
                      {rate.has_tracking && (
                        <span className="text-[10px] bg-green-500/10 text-green-400 px-2 py-0.5 rounded border border-green-500/20 flex items-center gap-1">
                          <Globe className="h-3 w-3" /> {t('追跡有', lang)}
                        </span>
                      )}
                      {rate.has_insurance ? (
                        <span className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded border border-blue-500/20 flex items-center gap-1">
                          <Shield className="h-3 w-3" /> {t('補償有', lang)}
                        </span>
                      ) : (
                        <span className="text-[10px] bg-red-500/10 text-red-400 px-2 py-0.5 rounded border border-red-500/20 flex items-center gap-1">
                          <Shield className="h-3 w-3" /> {t('補償無', lang)}
                        </span>
                      )}
                      {rate.max_size && (
                        <span className="text-[10px] bg-purple-500/10 text-purple-400 px-2 py-0.5 rounded border border-purple-500/20">
                          {rate.max_size}
                        </span>
                      )}
                    </div>
                    {rate.source_url && (
                      <a
                        href={rate.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-gray-500 hover:text-orange-400 flex items-center gap-1 transition-colors"
                      >
                        <ExternalLink className="h-3 w-3" />
                        {lang === 'ja' ? '参照元ページ' : 'Source URL'}
                      </a>
                    )}
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-orange-400">
                      {formatPrice(rate.fee_jpy)}
                    </p>
                    <p className="text-[10px] text-gray-500 mt-1">
                      {t('最終更新', lang)}: {new Date(rate.updated_at).toLocaleString(lang === 'ja' ? 'ja-JP' : 'en-US')}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
