'use client'

import { Category } from '@/lib/types'
import { cn } from '@/lib/utils'

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
  return (
    <aside className="w-full space-y-1">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3 px-3">
        カテゴリー
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
        すべて
      </button>
      {categories.map((category) => (
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
          {category.name}
        </button>
      ))}
    </aside>
  )
}
