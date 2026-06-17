'use client'

import { Category } from '@/lib/types'
import { cn } from '@/lib/utils'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { useBatchTranslation } from '@/hooks/useTranslation'

interface CategorySidebarProps {
  categories: Category[]
  selectedCategory: number | null
  onSelect: (id: number | null) => void
}

export default function CategorySidebar({
  categories,
  selectedCategory,
  onSelect,
}: CategorySidebarProps) {
  const { lang } = useLangStore()
  const names = categories.map((c) => c.name)
  const translatedNames = useBatchTranslation(names)

  return (
    <aside className="w-full space-y-1">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3 px-3">
        {t('カテゴリー', lang)}
      </h2>
      <button
        onClick={() => onSelect(null)}
        className={cn(
          'w-full text-left px-3 py-2 rounded-md text-sm transition-colors',
          selectedCategory === null
            ? 'bg-yellow-400/10 text-yellow-400 border border-yellow-400/20'
            : 'text-gray-300 hover:bg-white/5 hover:text-white'
        )}
      >
        {t('すべて', lang)}
      </button>
      {categories.map((category, i) => (
        <button
          key={category.id}
          onClick={() => onSelect(category.id)}
          className={cn(
            'w-full text-left px-3 py-2 rounded-md text-sm transition-colors',
            selectedCategory === category.id
              ? 'bg-yellow-400/10 text-yellow-400 border border-yellow-400/20'
              : 'text-gray-300 hover:bg-white/5 hover:text-white'
          )}
        >
          {translatedNames[i] || category.name}
        </button>
      ))}
    </aside>
  )
}
