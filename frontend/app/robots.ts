import type { MetadataRoute } from 'next'
import { SHOP_SITE_URL } from '@/lib/site-urls'

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: [
        '/admin/',
        '/cart',
        '/checkout/',
        '/orders',
        '/mypage/',
        '/sign-in',
        '/sign-up',
        '/login',
        '/register',
        '/auth/',
        '/verify/',
        '/cards/detail',
        '/api/',
      ],
    },
    sitemap: `${SHOP_SITE_URL}/sitemap.xml`,
    host: SHOP_SITE_URL,
  }
}
