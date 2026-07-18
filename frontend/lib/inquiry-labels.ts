/** Inquiry category options (single source of truth for the frontend). */

export const INQUIRY_CATEGORY_OPTIONS: { value: string; label: string }[] = [
  { value: 'product', label: '商品について' },
  { value: 'order_payment', label: '注文・支払いについて' },
  { value: 'shipping', label: '発送・配送について' },
  { value: 'refund', label: '返品・返金について' },
  { value: 'account', label: '会員情報について' },
  { value: 'points', label: 'ポイントについて' },
  { value: 'buyback', label: '買取について' },
  { value: 'bug', label: 'サイトの不具合' },
  { value: 'other', label: 'その他' },
]

export const INQUIRY_CATEGORY_PLACEHOLDER = 'カテゴリを選択してください'

export const INQUIRY_CATEGORY_LABELS: Record<string, string> = {
  product: '商品について',
  order_payment: '注文・支払いについて',
  shipping: '発送・配送について',
  refund: '返品・返金について',
  account: '会員情報について',
  points: 'ポイントについて',
  buyback: '買取について',
  bug: 'サイトの不具合',
  other: 'その他',
  // legacy slugs (existing inquiries / seeded templates)
  order: '注文・支払いについて',
  payment: '注文・支払いについて',
}

export const INQUIRY_STATUS_LABELS: Record<string, string> = {
  submitted: '送信済み',
  waiting_admin: 'ショップ返信待ち',
  waiting_customer: '購入者返信待ち',
  in_progress: '対応中',
  resolved: '解決済み',
  closed: '終了',
}

export const INQUIRY_STATUS_COLORS: Record<string, string> = {
  submitted: 'text-blue-600 bg-blue-500/10 border-blue-500/30',
  waiting_admin: 'text-amber-600 bg-amber-500/10 border-amber-500/30',
  waiting_customer: 'text-purple-600 bg-purple-500/10 border-purple-500/30',
  in_progress: 'text-sky-600 bg-sky-500/10 border-sky-500/30',
  resolved: 'text-green-600 bg-green-500/10 border-green-500/30',
  closed: 'text-gray-500 bg-gray-500/10 border-gray-500/30',
}

export function inquiryCategoryLabel(value: string): string {
  return INQUIRY_CATEGORY_LABELS[value] || value
}

export function inquiryStatusLabel(value: string): string {
  return INQUIRY_STATUS_LABELS[value] || value
}

/** Merge API categories with fixed fallback (API order wins when present). */
export function resolveInquiryCategories(
  fromApi?: { value: string; label: string }[] | null
): { value: string; label: string }[] {
  if (fromApi?.length) {
    const known = new Set(INQUIRY_CATEGORY_OPTIONS.map((c) => c.value))
    const merged = [...INQUIRY_CATEGORY_OPTIONS]
    for (const item of fromApi) {
      if (!known.has(item.value)) {
        merged.push(item)
      }
    }
    return merged
  }
  return INQUIRY_CATEGORY_OPTIONS
}

/** Template category slug may use legacy values from seeded data. */
export function inquiryTemplateMatchesCategory(
  templateCategory: string | null | undefined,
  selectedCategory: string
): boolean {
  if (!templateCategory) return true
  if (templateCategory === selectedCategory) return true
  if (
    selectedCategory === 'order_payment' &&
    (templateCategory === 'order' || templateCategory === 'payment')
  ) {
    return true
  }
  return false
}
