import { Metadata } from 'next'
import HomeClient from './HomeClient'
import { absoluteUrl, DEFAULT_DESCRIPTION, DEFAULT_TITLE } from '@/lib/seo'

export const metadata: Metadata = {
  title: DEFAULT_TITLE,
  description: DEFAULT_DESCRIPTION,
  alternates: {
    canonical: absoluteUrl('/'),
  },
  openGraph: {
    title: DEFAULT_TITLE,
    description: DEFAULT_DESCRIPTION,
    url: absoluteUrl('/'),
    images: ['/ogp.png'],
  },
}

export default function HomePage() {
  return <HomeClient />
}