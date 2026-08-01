/** Buyback catalog options aligned with card-vault-buylist public tabs. */

export const BUYBACK_CONDITION_OPTIONS = [
  { value: 'A', label: 'A（極美品）' },
  { value: 'B', label: 'B（美品）' },
  { value: 'C', label: 'C（軽い傷あり）' },
  { value: 'D', label: 'D（傷あり）' },
  { value: 'E', label: 'E（大きな傷あり）' },
  { value: 'ジャンク', label: 'ジャンク' },
] as const

export const BUYBACK_CATEGORY_OPTIONS = [
  { value: 'raw', label: '素体カード', hint: '単体カード・プロモ等' },
  { value: 'box', label: '未開封BOX', hint: 'シュリンク付きBOX' },
  { value: 'pack', label: '未開封パック', hint: '単品パック' },
  { value: 'psa', label: 'PSA鑑定品', hint: 'PSA等の鑑定済み商品' },
  { value: 'supply', label: 'サプライ', hint: 'スリーブ・デッキケース等' },
  { value: 'lottery', label: '抽選・キャンペーン', hint: '期間限定・数量限定' },
  { value: 'guarantee', label: '最低保証', hint: '最低保証対象商品' },
] as const

/** Legacy admin values — keep selectable when editing old rows. */
export const LEGACY_BUYBACK_CATEGORY_OPTIONS = [
  { value: 'graded', label: 'graded（旧・鑑定品）', hint: 'psa への移行を推奨' },
  { value: 'sealed', label: 'sealed（旧・未開封）', hint: 'box / pack への移行を推奨' },
  { value: 'accessory', label: 'accessory（旧・サプライ）', hint: 'supply への移行を推奨' },
] as const

export function getBuybackCategoryLabel(value: string): string {
  const all = [...BUYBACK_CATEGORY_OPTIONS, ...LEGACY_BUYBACK_CATEGORY_OPTIONS]
  return all.find((item) => item.value === value)?.label ?? value
}

export function getBuybackConditionLabel(value: string): string {
  if (value === 'default') return 'default（旧データ）'
  return BUYBACK_CONDITION_OPTIONS.find((item) => item.value === value)?.label ?? value
}

export function nextUnusedConditionCode(used: string[]): string | null {
  const usedSet = new Set(used.map((code) => code.trim()))
  for (const option of BUYBACK_CONDITION_OPTIONS) {
    if (!usedSet.has(option.value)) return option.value
  }
  return null
}

export function conditionOptionsForRow(
  currentValue: string,
  allValues: string[]
): Array<{ value: string; label: string; disabled?: boolean }> {
  const usedByOthers = new Set(
    allValues.filter((code) => code && code !== currentValue).map((code) => code.trim())
  )
  const options: Array<{ value: string; label: string; disabled?: boolean }> =
    BUYBACK_CONDITION_OPTIONS.map((option) => ({
      value: option.value,
      label: option.label,
      disabled: usedByOthers.has(option.value),
    }))
  if (currentValue && !options.some((option) => option.value === currentValue)) {
    options.unshift({
      value: currentValue,
      label: getBuybackConditionLabel(currentValue),
      disabled: false,
    })
  }
  return options
}
