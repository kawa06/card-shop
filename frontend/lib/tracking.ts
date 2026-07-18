/** Client-side tracking URL builder (mirrors backend/services/tracking_urls.py). */

const CARRIER_JAPAN_POST = 'japan_post'
const CARRIER_YAMATO = 'yamato'
const CARRIER_SAGAWA = 'sagawa'

const METHOD_CARRIER_MAP: Record<string, string> = {
  click_post: CARRIER_JAPAN_POST,
  teikei_post: CARRIER_JAPAN_POST,
  teigai_post: CARRIER_JAPAN_POST,
  letter_pack_light: CARRIER_JAPAN_POST,
  letter_pack_plus: CARRIER_JAPAN_POST,
  yu_pack_60: CARRIER_JAPAN_POST,
  yu_pack_80: CARRIER_JAPAN_POST,
  yu_pack_100: CARRIER_JAPAN_POST,
  ems: CARRIER_JAPAN_POST,
  takkyubin_compact: CARRIER_YAMATO,
  takkyubin_60: CARRIER_YAMATO,
  takkyubin_80: CARRIER_YAMATO,
  yamato_global: CARRIER_YAMATO,
}

function carrierFromText(text: string): string | null {
  if (/ヤマト|宅急便|kuroneko|yamato/i.test(text)) return CARRIER_YAMATO
  if (/佐川|sagawa/i.test(text)) return CARRIER_SAGAWA
  if (/日本郵便|郵便|ゆうパック|EMS|Japan Post/i.test(text)) return CARRIER_JAPAN_POST
  return null
}

export function resolveCarrier(
  shippingMethod: string | null | undefined,
  shippingCarrier: string | null | undefined
): string | null {
  if (shippingCarrier) {
    const fromText = carrierFromText(shippingCarrier)
    if (fromText) return fromText
  }
  if (shippingMethod) return METHOD_CARRIER_MAP[shippingMethod] || null
  return null
}

export function buildTrackingUrl(
  trackingNumber: string,
  shippingMethod?: string | null,
  shippingCarrier?: string | null
): string | null {
  const num = trackingNumber.trim()
  if (!num) return null

  const carrier = resolveCarrier(shippingMethod, shippingCarrier)
  if (carrier === CARRIER_YAMATO) {
    return `https://track.kuronekoyamato.co.jp/english/tracking/inquiry?number=${encodeURIComponent(num)}`
  }
  if (carrier === CARRIER_SAGAWA) {
    return `https://k2k.sagawa-exp.co.jp/p/web/okurijoinput.do?okurijoNo=${encodeURIComponent(num)}`
  }
  if (carrier === CARRIER_JAPAN_POST) {
    return (
      'https://trackings.post.japanpost.jp/services/srv/search/direct' +
      `?reqCodeNo1=${encodeURIComponent(num)}&locale=ja`
    )
  }
  return null
}

export function isTrackableShippingMethod(shippingMethod: string | null | undefined): boolean {
  if (!shippingMethod) return true
  return !['teikei_post', 'teigai_post'].includes(shippingMethod)
}
