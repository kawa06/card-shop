import type { MetadataRoute } from 'next'
import { DEFAULT_DESCRIPTION, SITE_NAME } from '@/lib/seo'
import { SHOP_SITE_URL } from '@/lib/site-urls'

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: SITE_NAME,
    short_name: SITE_NAME,
    description: DEFAULT_DESCRIPTION,
    start_url: '/',
    display: 'standalone',
    background_color: '#ffffff',
    theme_color: '#ffffff',
    lang: 'ja',
    icons: [
      {
        src: '/favicon.ico',
        sizes: 'any',
        type: 'image/x-icon',
      },
      {
        src: '/logo-main.png',
        sizes: '512x512',
        type: 'image/png',
      },
    ],
    id: SHOP_SITE_URL,
  }
}
