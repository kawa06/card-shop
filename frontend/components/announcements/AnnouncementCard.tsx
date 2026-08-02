'use client'

import Link from 'next/link'
import { Bell } from 'lucide-react'
import { Announcement } from '@/lib/types'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'

type AnnouncementCardProps = {
  item: Announcement
  href: string
}

function formatDate(value: string | null | undefined, lang: 'ja' | 'en') {
  if (!value) return '—'
  return new Date(value).toLocaleDateString(lang === 'ja' ? 'ja-JP' : 'en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export default function AnnouncementCard({ item, href }: AnnouncementCardProps) {
  const { lang } = useLangStore()
  const excerpt = item.content_excerpt || item.content.replace(/<[^>]+>/g, ' ').trim()

  return (
    <Link
      href={href}
      className="group block rounded-xl border border-gray-200 bg-gray-50 hover:border-yellow-400/40 hover:bg-yellow-50/30 transition-colors overflow-hidden"
    >
      <div className="flex gap-4 p-4 sm:p-5">
        <div className="w-20 h-20 sm:w-24 sm:h-24 rounded-lg bg-white border border-gray-200 overflow-hidden flex-shrink-0">
          {item.thumbnail ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={item.thumbnail} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-yellow-500/70">
              <Bell className="h-8 w-8" />
            </div>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            {item.is_new && (
              <span className="text-[10px] font-bold uppercase tracking-wide bg-red-500 text-white px-2 py-0.5 rounded">
                NEW
              </span>
            )}
            {!item.is_read && (
              <span className="text-[10px] font-bold bg-yellow-400 text-gray-950 px-2 py-0.5 rounded">
                {t('未読', lang)}
              </span>
            )}
            <span className="text-xs text-gray-500">{formatDate(item.publish_at || item.created_at, lang)}</span>
          </div>
          <h2 className="text-gray-900 font-semibold text-base sm:text-lg line-clamp-2 group-hover:text-yellow-700">
            {item.title}
          </h2>
          <p className="text-sm text-gray-500 mt-2 line-clamp-2">{excerpt}</p>
        </div>
      </div>
    </Link>
  )
}
