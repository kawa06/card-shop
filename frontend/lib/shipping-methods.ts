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

/** Intersection of allowed shipping methods across cart items (null = no restriction). */
export function intersectAllowedShippingMethods(
  items: Array<{ card: { allowed_shipping_methods?: string | null } }>
): string[] | null {
  if (!items.length) return null
  let intersection: Set<string> | null = null
  for (const item of items) {
    const methods = parseAllowedShippingMethods(item.card.allowed_shipping_methods)
    if (methods.length === 0) continue
    const methodSet = new Set(methods)
    if (intersection === null) {
      intersection = methodSet
    } else {
      const next = new Set<string>()
      intersection.forEach((code) => {
        if (methodSet.has(code)) next.add(code)
      })
      intersection = next
    }
  }
  return intersection ? Array.from(intersection) : null
}

export function serializeAllowedShippingMethods(codes: string[]): string | null {
  const unique = Array.from(new Set(codes.filter(Boolean)))
  return unique.length > 0 ? JSON.stringify(unique) : null
}
