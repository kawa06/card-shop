import { ClerkProvider } from '@clerk/nextjs'
import { ClerkBackendSync } from '@/components/auth/ClerkBackendSync'
import { ClerkTokenBridge } from '@/components/auth/ClerkTokenBridge'
import { AdminSessionSync } from '@/components/auth/AdminSessionSync'
import { clerkAppearance } from '@/lib/clerk/appearance'
import { clerkLocalization } from '@/lib/clerk/localization'
import { JsonLd } from '@/components/seo/JsonLd'
import {
  buildOrganizationJsonLd,
  buildWebsiteJsonLd,
  DEFAULT_DESCRIPTION,
  DEFAULT_TITLE,
  TWITTER_HANDLE,
} from '@/lib/seo'
import { SHOP_SITE_URL } from '@/lib/site-urls'
import type { Metadata, Viewport } from 'next'
import { Inter, Shippori_Mincho } from 'next/font/google'
import './globals.css'
import Header from '@/components/layout/Header'
import Footer from '@/components/layout/Footer'
import { Toaster } from '@/components/ui/toaster'
import { LangInit } from '@/components/LangInit'
import { RateInit } from '@/components/RateInit'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })
const shippori = Shippori_Mincho({ 
  weight: ['400', '700'],
  subsets: ['latin'],
  variable: '--font-shippori'
})

export const dynamic = 'force-dynamic'

export const viewport: Viewport = {
  themeColor: '#ffffff',
  width: 'device-width',
  initialScale: 1,
}

export const metadata: Metadata = {
  metadataBase: new URL(`${SHOP_SITE_URL}/`),
  title: {
    default: DEFAULT_TITLE,
    template: '%s | KRX TCG',
  },
  icons: {
    icon: '/favicon.ico',
    apple: '/logo-main.png',
  },
  description: DEFAULT_DESCRIPTION,
  openGraph: {
    type: 'website',
    siteName: 'KRX TCG',
    locale: 'ja_JP',
    url: SHOP_SITE_URL,
    title: DEFAULT_TITLE,
    description: DEFAULT_DESCRIPTION,
    images: [
      {
        url: '/ogp.png',
        width: 1200,
        height: 630,
        alt: 'KRX TCG',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    site: TWITTER_HANDLE,
    title: DEFAULT_TITLE,
    description: DEFAULT_DESCRIPTION,
    images: ['/ogp.png'],
  },
  robots: {
    index: true,
    follow: true,
  },
  verification: {
    google: 'DMTMs-DnAVdJ_8pURPDHh3Xg64UtljMFYdfS30SVfBc',
  },
  alternates: {
    languages: {
      'ja-JP': '/',
      'en-US': '/?lang=en',
    },
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ja">
      <body className={`${inter.variable} ${shippori.variable} font-sans min-h-screen bg-white text-gray-900 overflow-x-hidden`}>
        <JsonLd data={[buildOrganizationJsonLd(), buildWebsiteJsonLd()]} />
        <ClerkProvider localization={clerkLocalization} appearance={clerkAppearance}>
          <ClerkBackendSync />
          <ClerkTokenBridge />
          <AdminSessionSync />
          <LangInit />
          <RateInit />
          <div className="flex flex-col min-h-screen overflow-x-hidden">
          <Header />
          <main className="flex-1 w-full max-w-full overflow-x-hidden">{children}</main>
          <Footer />
          </div>
          <Toaster />
        </ClerkProvider>
      </body>
    </html>
  )
}
// Trigger redeploy 2026-06-20-v3