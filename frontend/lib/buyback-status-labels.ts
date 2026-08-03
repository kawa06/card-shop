export const BUYBACK_STATUS_LABELS: Record<string, string> = {
  draft: '下書き',
  submitted: '申請受付',
  identity_pending: '本人確認待ち',
  awaiting_shipment: '発送待ち',
  awaiting_visit: '来店待ち',
  shipped: '発送済み',
  received: '商品到着',
  store_visited: '来店済み',
  assessing: '査定中',
  assessed: '査定完了',
  awaiting_customer: '承認待ち',
  accepted: '承認済み',
  rejected: '買取不可',
  payout_pending: '支払準備中',
  paid: '支払完了',
  return_preparing: '返送準備中',
  returned: '返送済み',
  completed: '完了',
  cancelled: 'キャンセル',
  sent_back: '差戻し',
  on_hold: '保留',
}

export const BUYBACK_STATUS_FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'すべて' },
  { value: 'submitted', label: '申請受付' },
  { value: 'awaiting_shipment', label: '発送待ち' },
  { value: 'awaiting_visit', label: '来店待ち' },
  { value: 'assessing', label: '査定中' },
  { value: 'assessed', label: '査定完了' },
  { value: 'awaiting_customer', label: '承認待ち' },
  { value: 'payout_pending', label: '支払準備中' },
  { value: 'paid', label: '支払完了' },
  { value: 'completed', label: '完了' },
  { value: 'cancelled', label: 'キャンセル' },
  { value: 'on_hold', label: '保留' },
]

export function buybackStatusLabel(code: string | null | undefined, apiLabel?: string | null): string {
  if (!code) return '—'
  const local = BUYBACK_STATUS_LABELS[code] || code
  if (apiLabel && apiLabel !== code) return apiLabel
  return local
}
