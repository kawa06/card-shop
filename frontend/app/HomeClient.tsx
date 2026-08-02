'use client'

import Link from 'next/link'
import { Suspense } from 'react'
import { useState, useEffect, useCallback } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { Bell, ChevronRight } from 'lucide-react'
import { cardsApi, categoriesApi, announcementsApi, packsApi } from '@/lib/api'
import { Card, Category, Announcement, Pack } from '@/lib/types'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { useLocalizedNames } from '@/lib/localized'
import CardGrid from '@/components/cards/CardGrid'
import CategorySidebar from '@/components/cards/CategorySidebar'
import PackSidebar from '@/components/cards/PackSidebar'
import Pagination from '@/components/cards/Pagination'

function HomeContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const { lang } = useLangStore()

  const [cards, setCards] = useState<Card[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [packs, setPacks] = useState<Pack[]>([])
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [totalPages, setTotalPages] = useState(1)
  const [totalCards, setTotalCards] = useState(0)

  const currentPage = parseInt(searchParams.get('page') || '1')
  const searchQuery = searchParams.get('search') || ''
  const categoryId = searchParams.get('category') ? parseInt(searchParams.get('category')!) : null
  const packId = searchParams.get('pack') ? parseInt(searchParams.get('pack')!) : null

  useEffect(() => {
    let cancelled = false
    Promise.all([categoriesApi.getAll(), packsApi.getAll()]).then(([categoriesRes, packsRes]) => {
      if (cancelled) return
      setCategories(categoriesRes.data || [])
      setPacks(packsRes.data || [])
    })
    return () => {
      cancelled = true
    }
  }, [])

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    try {
      const params: Record<string, string | number> = {
        page: currentPage,
        per_page: 20,
      }
      if (searchQuery) params.q = searchQuery
      if (categoryId) params.category_id = categoryId
      if (packId) params.pack_id = packId

      const [cardsRes, announcementsRes] = await Promise.all([
        cardsApi.getAll(params),
        announcementsApi.getAll(lang),
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
      setAnnouncements(
        (announcementsRes.data || []).filter((a: Announcement) => a.is_active)
      )
    } catch (error) {
      console.error('Failed to fetch data:', error)
    } finally {
      setIsLoading(false)
    }
  }, [currentPage, searchQuery, categoryId, packId, lang])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const buildParams = (overrides: { category?: number | null; pack?: number | null; page?: string }) => {
    const params = new URLSearchParams()
    const cat = overrides.category !== undefined ? overrides.category : categoryId
    const pack = overrides.pack !== undefined ? overrides.pack : packId
    if (cat) params.set('category', cat.toString())
    if (pack) params.set('pack', pack.toString())
    if (searchQuery) params.set('search', searchQuery)
    params.set('page', overrides.page ?? '1')
    return params
  }

  const handleCategorySelect = (id: number | null) => {
    router.push(`/?${buildParams({ category: id, page: '1' }).toString()}`)
  }

  const handlePackSelect = (id: number | null) => {
    router.push(`/?${buildParams({ pack: id, page: '1' }).toString()}`)
  }

  const handlePageChange = (page: number) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set('page', page.toString())
    router.push(`/?${params.toString()}`)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const mobileCategoryNames = useLocalizedNames(categories)
  const mobilePackNames = useLocalizedNames(packs)

  return (
    <div className="min-h-screen bg-white overflow-x-hidden w-full max-w-full">
      {/* Announcements Banner */}
      {announcements.length > 0 && (
        <div className="bg-yellow-400/10 border-b border-yellow-400/20">
          <div className="container py-2 max-w-full">
            <div className="flex items-center gap-2 overflow-x-auto max-w-full">
              <Bell className="h-4 w-4 text-yellow-400 flex-shrink-0" />
              {announcements.map((announcement, i) => (
                <Link
                  key={announcement.id}
                  href={`/mypage/announcements/${announcement.id}`}
                  className="flex items-center gap-2 text-sm text-yellow-700 whitespace-nowrap hover:underline"
                >
                  {i > 0 && <span className="text-yellow-400/30">|</span>}
                  <span className="text-yellow-600 font-medium">{announcement.title}</span>
                  <ChevronRight className="h-3 w-3 text-yellow-400/50" />
                  <span className="hidden sm:inline truncate max-w-[240px]">
                    {(announcement.content || '').replace(/<[^>]+>/g, ' ').trim()}
                  </span>
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="container py-6 max-w-full overflow-x-hidden">
        <div className="flex gap-4 sm:gap-6 min-w-0">
          {/* Sidebar */}
          <aside className="hidden lg:block w-48 flex-shrink-0">
            <div className="sticky top-24">
              <CategorySidebar
                categories={categories}
                selectedCategory={categoryId}
                onSelect={handleCategorySelect}
              />
              <PackSidebar
                packs={packs}
                selectedPack={packId}
                onSelect={handlePackSelect}
              />
            </div>
          </aside>

          {/* Cards */}
          <div className="flex-1 min-w-0">
            {/* Mobile filters */}
            <div className="lg:hidden mb-4 space-y-3">
              <div className="flex gap-2 overflow-x-auto pb-2">
                <button
                  onClick={() => handleCategorySelect(null)}
                  className={`flex-shrink-0 px-3 py-1.5 rounded-full text-sm border transition-colors ${
                    categoryId === null
                      ? 'bg-yellow-400/10 text-yellow-400 border-yellow-400/30'
                      : 'border-gray-200 text-gray-500 hover:text-gray-900'
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
                        : 'border-gray-200 text-gray-500 hover:text-gray-900'
                    }`}
                  >
                    {mobileCategoryNames[idx] || cat.name}
                  </button>
                ))}
              </div>
              {packs.length > 0 && (
                <div className="flex gap-2 overflow-x-auto pb-2">
                  <button
                    onClick={() => handlePackSelect(null)}
                    className={`flex-shrink-0 px-3 py-1.5 rounded-full text-sm border transition-colors ${
                      packId === null
                        ? 'bg-sky-400/10 text-sky-600 border-sky-400/30'
                        : 'border-gray-200 text-gray-500 hover:text-gray-900'
                    }`}
                  >
                    {t('全パック', lang)}
                  </button>
                  {packs.map((pack, idx) => (
                    <button
                      key={pack.id}
                      onClick={() => handlePackSelect(pack.id)}
                      className={`flex-shrink-0 px-3 py-1.5 rounded-full text-sm border transition-colors ${
                        packId === pack.id
                          ? 'bg-sky-400/10 text-sky-600 border-sky-400/30'
                          : 'border-gray-200 text-gray-500 hover:text-gray-900'
                      }`}
                    >
                      {mobilePackNames[idx] || pack.name}
                    </button>
                  ))}
                </div>
              )}
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

export default function HomeClient() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-gray-400 animate-pulse">{t('読み込み中...', 'ja')}</div>
      </div>
    }>
      <HomeContent />
    </Suspense>
  )
}