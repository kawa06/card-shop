import { useLangStore } from '@/store/lang'
import { useRateStore } from '@/store/rate'

const DEFAULT_RATE = 150

/**
 * 価格を言語設定に合わせてフォーマットする
 * @param price 円単位の価格
 * @param lang 言語 ('ja' | 'en')
 * @returns フォーマットされた価格文字列
 */
export const formatPrice = (price: number, lang: 'ja' | 'en' = 'ja') => {
  if (lang === 'ja') {
    return `¥${price.toLocaleString()}`
  }

  const rate = useRateStore.getState().usdJpyRate || DEFAULT_RATE
  // 換算ロジック: Math.round(price / rate * 100) / 100 で 小数点以下2桁に丸める
  const usdPrice = Math.round((price / rate) * 100) / 100
  
  // toLocaleString('en-US', { style: 'currency', currency: 'USD' }) で .00 形式を出力
  return usdPrice.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
}

/**
 * コンポーネント内で使用する価格フォーマット用フック
 */
export const usePrice = () => {
  const { lang } = useLangStore()
  const { usdJpyRate } = useRateStore()
  
  return {
    formatPrice: (price: number) => formatPrice(price, lang),
    lang,
    rate: usdJpyRate
  }
}
