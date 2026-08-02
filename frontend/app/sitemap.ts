import type { MetadataRoute } from 'next'
import { SHOP_SITE_URL } from '@/lib/site-urls'

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ||
  'https://backend-production-054e.up.railway.app'

type CardListResponse = {
  items: Array<{ id: number; updated_at?: string | null }>
  total: number
  pages?: number
}

async function fetchAllCardUrls(): Promise<MetadataRoute.Sitemap> {
  const urls: MetadataRoute.Sitemap = []

  try {
    let page = 1
    let totalPages = 1

    while (page <= totalPages && page <= 100) {
      const res = await fetch(
        `${API_BASE}/api/cards?per_page=100&page=${page}&sort=created_at_desc`,
        { next: { revalidate: 3600 } }
      )
      if (!res.ok) {
        console.error(`sitemap: cards API returned ${res.status} on page ${page}`)
        break
      }

      const data = (await res.json()) as CardListResponse
      totalPages = data.pages || Math.ceil((data.total || 0) / 100) || 1

      for (const card of data.items || []) {
        if (!card?.id) continue
        urls.push({
          url: `${SHOP_SITE_URL}/cards/${card.id}`,
          lastModified: card.updated_at ? new Date(card.updated_at) : new Date(),
          changeFrequency: 'daily',
          priority: 0.8,
        })
      }

      if (!data.items?.length) break
      page += 1
    }
  } catch (error) {
    console.error('sitemap: failed to fetch card URLs', error)
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

export const revalidate = 3600
