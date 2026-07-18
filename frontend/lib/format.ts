import { useLangStore } from '@/store/lang'
import { useRateStore } from '@/store/rate'

const DEFAULT_RATE = 150

export interface CardPriceFields {
  price: number
  price_usd?: number | null
}

/**
 * USD amount shown on English storefront for a card.
 */
export function getCardDisplayUsd(
  card: CardPriceFields,
  rate: number = DEFAULT_RATE
): number {
  if (card.price_usd != null && card.price_usd > 0) {
    return Math.round(card.price_usd * 100) / 100
  }
  const effectiveRate = rate > 0 ? rate : DEFAULT_RATE
  return Math.round((card.price / effectiveRate) * 100) / 100
}

/**
 * JPY checkout amount derived from USD when admin priced in dollars.
 */
export function jpyFromUsd(usd: number, rate: number = DEFAULT_RATE): number {
  const effectiveRate = rate > 0 ? rate : DEFAULT_RATE
  return Math.round(usd * effectiveRate)
}

/**
 * Format a plain JPY amount (shipping, orders, etc.).
 */
export const formatPrice = (price: number, lang: 'ja' | 'en' = 'ja') => {
  if (lang === 'ja') {
    return `¥${price.toLocaleString()}`
  }

  const rate = useRateStore.getState().usdJpyRate || DEFAULT_RATE
  const usdPrice = Math.round((price / rate) * 100) / 100

  return usdPrice.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

/**
 * Format a card price — uses optional fixed USD override on English storefront.
 */
export const formatCardPrice = (
  card: CardPriceFields,
  lang: 'ja' | 'en' = 'ja'
) => {
  if (lang === 'ja') {
    return `¥${card.price.toLocaleString()}`
  }

  const rate = useRateStore.getState().usdJpyRate || DEFAULT_RATE
  const usdPrice = getCardDisplayUsd(card, rate)

  return usdPrice.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

/**
 * Format card line total (unit × quantity) for cart/checkout display.
 */
export const formatCardLineTotal = (
  card: CardPriceFields,
  quantity: number,
  lang: 'ja' | 'en' = 'ja'
) =>
  formatCardPrice(
    {
      price: card.price * quantity,
      price_usd: card.price_usd != null ? card.price_usd * quantity : null,
    },
    lang
  )

/**
 * Component hook for price formatting.
 */
export const usePrice = () => {
  const { lang } = useLangStore()
  const { usdJpyRate } = useRateStore()

  return {
    formatPrice: (price: number) => formatPrice(price, lang),
    formatCardPrice: (card: CardPriceFields) => formatCardPrice(card, lang),
    formatCardLineTotal: (card: CardPriceFields, quantity: number) =>
      formatCardLineTotal(card, quantity, lang),
    lang,
    rate: usdJpyRate,
  }
}
