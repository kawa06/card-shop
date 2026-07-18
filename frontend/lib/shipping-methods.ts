/** カードに設定された許可発送方法を配列で返す（未設定・空 = 制限なし） */
export function parseAllowedShippingMethods(raw: string | null | undefined): string[] {
  if (!raw || raw === 'null' || raw === '[]') return []
  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) {
      return parsed.filter((c): c is string => typeof c === 'string' && c.length > 0).map((c) => (c === 'international' ? 'ems' : c))
    }
  } catch {
    // カンマ区切りの旧形式
    return raw.split(',').map((s) => s.trim()).filter(Boolean)
  }
  return []
}

export function serializeAllowedShippingMethods(codes: string[]): string | null {
  const unique = Array.from(new Set(codes.filter(Boolean)))
  return unique.length > 0 ? JSON.stringify(unique) : null
}
