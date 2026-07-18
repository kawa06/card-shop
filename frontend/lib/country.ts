/** ISO country codes used in checkout (must match backend/services/countries.py). */
export const CHECKOUT_COUNTRIES = [
  { code: 'JP', ja: '日本', en: 'Japan' },
  { code: 'US', ja: 'アメリカ合衆国', en: 'United States' },
  { code: 'CN', ja: '中国', en: 'China' },
  { code: 'KR', ja: '韓国', en: 'South Korea' },
  { code: 'TW', ja: '台湾', en: 'Taiwan' },
  { code: 'HK', ja: '香港', en: 'Hong Kong' },
  { code: 'SG', ja: 'シンガポール', en: 'Singapore' },
  { code: 'TH', ja: 'タイ', en: 'Thailand' },
  { code: 'GB', ja: 'イギリス', en: 'United Kingdom' },
  { code: 'FR', ja: 'フランス', en: 'France' },
  { code: 'DE', ja: 'ドイツ', en: 'Germany' },
  { code: 'IT', ja: 'イタリア', en: 'Italy' },
  { code: 'ES', ja: 'スペイン', en: 'Spain' },
  { code: 'CA', ja: 'カナダ', en: 'Canada' },
  { code: 'AU', ja: 'オーストラリア', en: 'Australia' },
  { code: 'NZ', ja: 'ニュージーランド', en: 'New Zealand' },
] as const

const DOMESTIC_ALIASES = new Set(['JP', 'Japan', '日本'])

/** Normalize stored profile / form values to ISO code (defaults to JP). */
export function normalizeCountryCode(value: string | null | undefined): string {
  if (!value) return 'JP'
  const trimmed = value.trim()
  if (DOMESTIC_ALIASES.has(trimmed)) return 'JP'
  const byCode = CHECKOUT_COUNTRIES.find((c) => c.code === trimmed)
  if (byCode) return byCode.code
  const byJa = CHECKOUT_COUNTRIES.find((c) => c.ja === trimmed)
  if (byJa) return byJa.code
  const byEn = CHECKOUT_COUNTRIES.find((c) => c.en === trimmed)
  if (byEn) return byEn.code
  return trimmed
}

export function isDomesticJapan(countryCode: string | null | undefined): boolean {
  return normalizeCountryCode(countryCode) === 'JP'
}

export function countryDisplayName(code: string, lang: 'ja' | 'en'): string {
  const normalized = normalizeCountryCode(code)
  const row = CHECKOUT_COUNTRIES.find((c) => c.code === normalized)
  if (!row) return code
  return lang === 'ja' ? row.ja : row.en
}
