'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'
import { ArrowLeft, Bell } from 'lucide-react'
import { announcementsApi } from '@/lib/api'
import { Announcement } from '@/lib/types'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { useAuthStore } from '@/store/auth'
import AnnouncementHtml from '@/components/announcements/AnnouncementHtml'
import ImageLightbox from '@/components/announcements/ImageLightbox'

export default function AnnouncementDetailPage() {
  const params = useParams()
  const router = useRouter()
  const id = Number(params.id)
  const { isSignedIn, isLoaded } = useAuth()
  const { isAuthenticated, hasHydrated } = useAuthStore()
  const { lang } = useLangStore()
  const [detail, setDetail] = useState<Announcement | null>(null)
  const [lightbox, setLightbox] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!isLoaded || !hasHydrated || !id) return
    if (!isSignedIn && !isAuthenticated) {
      router.push('/sign-in')
      return
    }
    setIsLoading(true)
    announcementsApi
      .getById(id, lang)
      .then((res) => setDetail(res.data))
      .catch(() => setDetail(null))
      .finally(() => setIsLoading(false))
  }, [id, lang, isLoaded, hasHydrated, isSignedIn, isAuthenticated, router])

  const publishLabel = detail?.publish_at || detail?.created_at

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-3xl">
        <Link
          href="/mypage/announcements"
          className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900 mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('お知らせ一覧', lang)}
        </Link>

        {isLoading ? (
          <div className="space-y-4 animate-pulse">
            <div className="h-8 bg-gray-100 rounded w-2/3" />
            <div className="h-4 bg-gray-100 rounded w-1/3" />
            <div className="h-48 bg-gray-100 rounded" />
          </div>
        ) : !detail ? (
          <div className="rounded-xl border border-gray-200 p-8 text-center text-gray-500">
            {lang === 'ja' ? 'お知らせが見つかりません' : 'Announcement not found'}
          </div>
        ) : (
          <article className="space-y-6">
            <header className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Bell className="h-5 w-5 text-yellow-500" />
                {detail.is_new && (
                  <span className="text-[10px] font-bold uppercase bg-red-500 text-white px-2 py-0.5 rounded">
                    NEW
                  </span>
                )}
                {publishLabel && (
                  <time className="text-sm text-gray-500">
                    {new Date(publishLabel).toLocaleDateString(lang === 'ja' ? 'ja-JP' : 'en-US', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                    })}
                  </time>
                )}
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 leading-tight">{detail.title}</h1>
            </header>

            {detail.thumbnail && (
              <button type="button" className="block w-full" onClick={() => setLightbox(detail.thumbnail || null)}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={detail.thumbnail}
                  alt=""
                  className="w-full max-h-[420px] object-cover rounded-xl border border-gray-200"
                />
              </button>
            )}

            {detail.images && detail.images.length > 0 && (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {detail.images.map((image) => (
                  <button
                    key={image.id}
                    type="button"
                    className="rounded-lg overflow-hidden border border-gray-200 bg-gray-50"
                    onClick={() => setLightbox(image.image_url)}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={image.image_url} alt="" className="w-full h-32 object-cover" />
                  </button>
                ))}
              </div>
            )}

            <div className="rounded-xl border border-gray-200 bg-gray-50/50 p-5 sm:p-8">
              <AnnouncementHtml html={detail.content} onImageClick={setLightbox} />
            </div>
          </article>
        )}
      </div>
      <ImageLightbox src={lightbox} onClose={() => setLightbox(null)} />
    </div>
  )
}
