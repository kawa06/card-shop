import { useLangStore } from '@/store/lang'
import { useBatchTranslation, useTranslation } from '@/hooks/useTranslation'

export interface LocalizedNameFields {
  name: string
  name_en?: string | null
}

export function localizedName(
  item: LocalizedNameFields | null | undefined,
  lang: 'ja' | 'en'
): string {
  if (!item) return ''
  if (lang === 'en' && item.name_en?.trim()) return item.name_en.trim()
  return item.name
}

export function displayLocalizedName(
  item: LocalizedNameFields,
  lang: 'ja' | 'en',
  translatedFallback?: string
): string {
  if (lang === 'en' && item.name_en?.trim()) return item.name_en.trim()
  if (lang === 'en' && translatedFallback) return translatedFallback
  return item.name
}

export function useLocalizedName(item: LocalizedNameFields | null | undefined): string {
  const { lang } = useLangStore()
  const translated = useTranslation(item?.name)
  if (!item) return ''
  return displayLocalizedName(item, lang, translated)
}

export function useLocalizedNames(items: LocalizedNameFields[]): string[] {
  const { lang } = useLangStore()
  const fallbackTexts = items.map((item) => item.name)
  const translatedNames = useBatchTranslation(fallbackTexts)
  return items.map((item, i) => displayLocalizedName(item, lang, translatedNames[i]))
}
