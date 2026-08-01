import { SHOP_SITE_URL } from '@/lib/site-urls'

export const SITE_NAME = 'KRX TCG'
export const SITE_TAGLINE = 'トレーディングカード販売サイト'
export const DEFAULT_TITLE = `${SITE_NAME} | ${SITE_TAGLINE}`
export const DEFAULT_DESCRIPTION =
  'ポケモンカード・ワンピースなど人気カードを取り扱う専門店。最新のカードからレアなアイテムまで豊富に取り揃えています。'
export const TWITTER_HANDLE = '@oripa_kawa'
export const CONTACT_EMAIL = 'oripakawa@gmail.com'

export function absoluteUrl(path = '/'): string {
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path
  }
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${SHOP_SITE_URL}${normalized}`
}

export function buildOrganizationJsonLd() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: SITE_NAME,
    url: SHOP_SITE_URL,
    logo: absoluteUrl('/logo-main.png'),
    email: CONTACT_EMAIL,
    sameAs: ['https://twitter.com/oripa_kawa'],
  }
}

export function buildWebsiteJsonLd() {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: SITE_NAME,
    url: SHOP_SITE_URL,
    description: DEFAULT_DESCRIPTION,
    inLanguage: 'ja-JP',
    potentialAction: {
      '@type': 'SearchAction',
      target: {
        '@type': 'EntryPoint',
        urlTemplate: `${SHOP_SITE_URL}/?q={search_term_string}`,
      },
      'query-input': 'required name=search_term_string',
    },
  }
}

export function buildBreadcrumbJsonLd(items: Array<{ name: string; path: string }>) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: absoluteUrl(item.path),
    })),
  }
}

export function buildProductJsonLd(card: {
  id: number
  name: string
  image_url?: string | null
  description?: string | null
  condition?: string | null
  price: number
  stock: number
}) {
  const conditionLabel: Record<string, string> = {
    a: 'A（美品）',
    b: 'B（良品）',
    c: 'C（並品）',
    d: 'D（傷あり）',
    e: 'E（難あり）',
  }
  const condition = conditionLabel[card.condition || ''] || card.condition || ''
  const productUrl = absoluteUrl(`/cards/${card.id}`)

  return {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: card.name,
    image: card.image_url || undefined,
    description: card.description || `${card.name} - 状態${condition}`,
    sku: String(card.id),
    brand: {
      '@type': 'Brand',
      name: SITE_NAME,
    },
    offers: {
      '@type': 'Offer',
      price: card.price,
      priceCurrency: 'JPY',
      availability:
        card.stock > 0 ? 'https://schema.org/InStock' : 'https://schema.org/OutOfStock',
      url: productUrl,
      seller: {
        '@type': 'Organization',
        name: SITE_NAME,
      },
    },
  }
}
