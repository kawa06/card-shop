'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft, MessageSquare, Plus } from 'lucide-react'
import { useBackendAuth } from '@/hooks/useBackendAuth'
import { inquiriesApi } from '@/lib/api'
import { InquiryListItem } from '@/lib/types'
import { inquiryCategoryLabel, inquiryStatusLabel, INQUIRY_STATUS_COLORS } from '@/lib/inquiry-labels'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { Button } from '@/components/ui/button'

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('ja-JP')
}

export default function InquiriesPage() {
  const router = useRouter()
  const { isLoggedIn, isReady, requireAuth } = useBackendAuth()
  const { lang } = useLangStore()
  const [items, setItems] = useState<InquiryListItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const load = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await inquiriesApi.list()
      setItems(res.data || [])
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!isMounted || !isReady) return
    if (!isLoggedIn) {
      router.push('/sign-in')
      return
    }
    void requireAuth().then((token) => {
      if (token) void load()
    })
  }, [isMounted, isReady, isLoggedIn, router, requireAuth, load])

  if (!isMounted || !isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-3xl">
        <div className="flex items-center justify-between mb-6">
          <Link href="/mypage" className="inline-flex items-center gap-2 text-gray-500 hover:text-gray-900 text-sm">
            <ArrowLeft className="h-4 w-4" />
            {t('マイページ', lang)}
          </Link>
          <Button asChild size="sm">
            <Link href="/mypage/inquiries/new">
              <Plus className="h-4 w-4 mr-1" />
              {lang === 'ja' ? '新規お問い合わせ' : 'New inquiry'}
            </Link>
          </Button>
        </div>

        <div className="flex items-center gap-3 mb-6">
          <MessageSquare className="h-6 w-6 text-yellow-400" />
          <h1 className="text-2xl font-bold text-gray-900">
            {lang === 'ja' ? '問い合わせ履歴' : 'Inquiry history'}
          </h1>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 bg-gray-50 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="bg-gray-50 rounded-lg border border-dashed border-gray-200 p-10 text-center">
            <p className="text-gray-500 text-sm mb-4">
              {lang === 'ja' ? '問い合わせ履歴はありません' : 'No inquiries yet'}
            </p>
            <Button asChild variant="outline">
              <Link href="/mypage/inquiries/new">
                {lang === 'ja' ? 'お問い合わせする' : 'Contact us'}
              </Link>
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
              <Link key={item.id} href={`/mypage/inquiries/${item.id}`}>
                <div
                  className={`rounded-lg border p-4 hover:border-yellow-400/40 transition-colors ${
                    item.customer_unread_count > 0 ? 'border-yellow-400/50 bg-yellow-50/30' : 'border-gray-200 bg-gray-50'
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
                    <div>
                      <p className="text-xs text-gray-500">{item.inquiry_number}</p>
                      <p className="text-gray-900 font-medium">{item.subject}</p>
                    </div>
                    {item.customer_unread_count > 0 && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-400 text-gray-950 font-medium">
                        {lang === 'ja' ? '未読' : 'Unread'}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs">
                    <span className="text-gray-500">{inquiryCategoryLabel(item.category)}</span>
                    <span
                      className={`px-2 py-0.5 rounded border ${INQUIRY_STATUS_COLORS[item.status] || 'text-gray-600 bg-gray-100 border-gray-200'}`}
                    >
                      {inquiryStatusLabel(item.status)}
                    </span>
                    {item.related_order_number && (
                      <span className="text-gray-500">注文: {item.related_order_number}</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 mt-2">{formatDate(item.last_message_at || item.updated_at || item.created_at)}</p>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
