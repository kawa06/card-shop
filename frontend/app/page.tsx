'use client'

import { Suspense } from 'react'
import { useState, useEffect, useCallback } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { Bell, ChevronRight } from 'lucide-react'
import { cardsApi, categoriesApi, announcementsApi } from '@/lib/api'
import { Card, Category, Announcement } from '@/lib/types'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { useTranslation, useBatchTranslation } from '@/hooks/useTranslation'
import CardGrid from '@/components/cards/CardGrid'
import CategorySidebar from '@/components/cards/CategorySidebar'
import Pagination from '@/components/cards/Pagination'

function HomeContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const { lang } = useLangStore()

  const [cards, setCards] = useState<Card[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [totalPages, setTotalPages] = useState(1)
  const [totalCards, setTotalCards] = useState(0)

  const currentPage = parseInt(searchParams.get('page') || '1')
  const searchQuery = searchParams.get('search') || ''
  const categoryId = searchParams.get('category') ? parseInt(searchParams.get('category')!) : null

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    try {
      const params: Record<string, string | number> = {
        page: currentPage,
        size: 20,
      }
      if (searchQuery) params.search = searchQuery
      if (categoryId) params.category_id = categoryId

      const [cardsRes, categoriesRes, announcementsRes] = await Promise.all([
        cardsApi.getAll(params),
        categoriesApi.getAll(),
        announcementsApi.getAll(),
      ])

      const cardsData = cardsRes.data
      if (Array.isArray(cardsData)) {
        setCards(cardsData)
        setTotalPages(1)
        setTotalCards(cardsData.length)
      } else {
        setCards(cardsData.items || [])
        setTotalPages(cardsData.pages || 1)
        setTotalCards(cardsData.total || 0)
      }
      setCategories(categoriesRes.data || [])
      setAnnouncements(
        (announcementsRes.data || []).filter((a: Announcement) => a.is_active)
      )
    } catch (error) {
      console.error('Failed to fetch data:', error)
    } finally {
      setIsLoading(false)
    }
  }, [currentPage, searchQuery, categoryId])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleCategorySelect = (id: number | null) => {
    const params = new URLSearchParams()
    if (id) params.set('category', id.toString())
    if (searchQuery) params.set('search', searchQuery)
    params.set('page', '1')
    router.push(`/?${params.toString()}`)
  }

  const handlePageChange = (page: number) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set('page', page.toString())
    router.push(`/?${params.toString()}`)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const mobileCategoryNames = useBatchTranslation(categories.map((c) => c.name))

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Announcements Banner */}
      {announcements.length > 0 && (
        <div className="bg-yellow-400/10 border-b border-yellow-400/20">
          <div className="container py-2">
            <div className="flex items-center gap-2 overflow-x-auto">
              <Bell className="h-4 w-4 text-yellow-400 flex-shrink-0" />
              {announcements.map((announcement, i) => (
                <TranslatedAnnouncement key={announcement.id} announcement={announcement} i={i} />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Hero */}
      <div className="relative overflow-hidden bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 border-b border-white/5">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-yellow-900/10 via-transparent to-transparent" />
        <div className="container py-10 relative">
          <h1 className="text-3xl md:text-4xl font-bold text-white mb-2">
            {t('トレーディングカード専門店', lang)}
          </h1>
          <p className="text-gray-400">
            {searchQuery
              ? (lang === 'ja'
                ? `"${searchQuery}" の検索結果: ${totalCards}件`
                : `Search results for "${searchQuery}": ${totalCards} results`)
              : (lang === 'ja'
                ? `${totalCards}枚のカードから選ぼう`
                : `${totalCards} cards to choose from`)}
          </p>
        </div>
      </div>

      {/* Main Content */}
      <div className="container py-6">
        <div className="flex gap-6">
          {/* Sidebar */}
          <aside className="hidden lg:block w-48 flex-shrink-0">
            <div className="sticky top-24">
              <CategorySidebar
                categories={categories}
                selectedCategory={categoryId}
                onSelect={handleCategorySelect}
              />
            </div>
          </aside>

          {/* Cards */}
          <div className="flex-1 min-w-0">
            {/* Mobile category filter */}
            <div className="lg:hidden mb-4 flex gap-2 overflow-x-auto pb-2">
              <button
                onClick={() => handleCategorySelect(null)}
                className={`flex-shrink-0 px-3 py-1.5 rounded-full text-sm border transition-colors ${
                  categoryId === null
                    ? 'bg-yellow-400/10 text-yellow-400 border-yellow-400/30'
                    : 'border-white/10 text-gray-400 hover:text-white'
                }`}
              >
                {t('すべて', lang)}
              </button>
              {categories.map((cat, idx) => (
                <button
                  key={cat.id}
                  onClick={() => handleCategorySelect(cat.id)}
                  className={`flex-shrink-0 px-3 py-1.5 rounded-full text-sm border transition-colors ${
                    categoryId === cat.id
                      ? 'bg-yellow-400/10 text-yellow-400 border-yellow-400/30'
                      : 'border-white/10 text-gray-400 hover:text-white'
                  }`}
                >
                  {mobileCategoryNames[idx] || cat.name}
                </button>
              ))}
            </div>

            <CardGrid cards={cards} isLoading={isLoading} />
            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={handlePageChange}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

function TranslatedAnnouncement({ announcement, i }: { announcement: Announcement; i: number }) {
  const title = useTranslation(announcement.title)
  const content = useTranslation(announcement.content)
  return (
    <span className="flex items-center gap-2 text-sm text-yellow-200/80 whitespace-nowrap">
      {i > 0 && <span className="text-yellow-400/30">|</span>}
      <span className="text-yellow-400 font-medium">{title}</span>
      <ChevronRight className="h-3 w-3 text-yellow-400/50" />
      <span>{content}</span>
    </span>
  )
}

export default function HomePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-gray-400 animate-pulse">{t('読み込み中...', 'ja')}</div>
      </div>
    }>
      <HomeContent />
    </Suspense>
  )
}
