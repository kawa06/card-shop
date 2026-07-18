'use client'

import { Pack } from '@/lib/types'
import { cn } from '@/lib/utils'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { useLocalizedNames } from '@/lib/localized'

interface PackSidebarProps {
  packs: Pack[]
  selectedPack: number | null
  onSelect: (id: number | null) => void
}

export default function PackSidebar({
  packs,
  selectedPack,
  onSelect,
}: PackSidebarProps) {
  const { lang } = useLangStore()
  const packNames = useLocalizedNames(packs)

  if (packs.length === 0) return null

  return (
    <aside className="w-full space-y-1 mt-6">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3 px-3">
        {t('パック', lang)}
      </h2>
      <button
        onClick={() => onSelect(null)}
        className={cn(
          'w-full text-left px-3 py-2 rounded-md text-sm transition-colors',
          selectedPack === null
            ? 'bg-sky-400/10 text-sky-600 border border-sky-400/20'
            : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
        )}
      >
        {t('すべて', lang)}
      </button>
      {packs.map((pack, i) => (
        <button
          key={pack.id}
          onClick={() => onSelect(pack.id)}
          className={cn(
            'w-full text-left px-3 py-2 rounded-md text-sm transition-colors',
            selectedPack === pack.id
              ? 'bg-sky-400/10 text-sky-600 border border-sky-400/20'
              : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
          )}
        >
          {packNames[i] || pack.name}
        </button>
      ))}
    </aside>
  )
}
