export const INQUIRY_CATEGORY_LABELS: Record<string, string> = {
  order: '注文について',
  payment: '支払いについて',
  shipping: '発送について',
  product: '商品について',
  points: 'ポイントについて',
  account: '会員情報について',
  bug: 'サイトの不具合について',
  buyback: '買取について',
  other: 'その他',
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
