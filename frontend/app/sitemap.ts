import type { MetadataRoute } from 'next'
import { SHOP_SITE_URL } from '@/lib/site-urls'

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ||
  'https://backend-production-054e.up.railway.app'

type CardListResponse = {
  items: Array<{ id: number; updated_at?: string | null }>
  total: number
}

async function fetchAllCardUrls(): Promise<MetadataRoute.Sitemap> {
  const urls: MetadataRoute.Sitemap = []
  let page = 1
  let total = 0

  while (page === 1 || urls.length < total) {
    const res = await fetch(`${API_BASE}/api/cards?per_page=100&page=${page}&sort=created_at_desc`, {
      next: { revalidate: 3600 },
    })
    if (!res.ok) {
      break
    }
    const data = (await res.json()) as CardListResponse
    total = data.total || 0
    for (const card of data.items || []) {
      urls.push({
        url: `${SHOP_SITE_URL}/cards/${card.id}`,
        lastModified: card.updated_at ? new Date(card.updated_at) : new Date(),
        changeFrequency: 'daily',
        priority: 0.8,
      })
    }
    if (!data.items?.length) {
      break
    }
    page += 1
    if (page > 50) {
      break
    }
  }

  return urls
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticPages: MetadataRoute.Sitemap = [
    {
      url: SHOP_SITE_URL,
      changeFrequency: 'daily',
      priority: 1,
    },
    {
      url: `${SHOP_SITE_URL}/terms`,
      changeFrequency: 'monthly',
      priority: 0.3,
    },
    {
      url: `${SHOP_SITE_URL}/privacy`,
      changeFrequency: 'monthly',
      priority: 0.3,
    },
    {
      url: `${SHOP_SITE_URL}/tokusho`,
      changeFrequency: 'monthly',
      priority: 0.4,
    },
    {
      url: `${SHOP_SITE_URL}/shipping-policy`,
      changeFrequency: 'monthly',
      priority: 0.3,
    },
  ]

  const cardUrls = await fetchAllCardUrls()
  return [...staticPages, ...cardUrls]
}
