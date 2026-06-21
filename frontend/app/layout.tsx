// Version: 2026-06-20-v2
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
  themeColor: '#030712',
  width: 'device-width',
  initialScale: 1,
}

export const metadata: Metadata = {
  metadataBase: new URL('https://frontend-one-topaz-20.vercel.app/'),
  title: {
    default: 'KRX TCG | トレーディングカード販売サイト',
    template: '%s | KRX TCG',
  },
  icons: {
    icon: '/favicon.ico',
    apple: '/logo-main.png',
  },
  description: 'ポケモンカード・ワンピースなど人気カードを取り扱う専門店',
  openGraph: {
    type: 'website',
    siteName: 'KRX TCG',
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
    site: '@oripa_kawa',
  },
  robots: {
    index: true,
    follow: true,
  },
  verification: {
    google: 'DMTMs-DnAVdJ_8pURPDHh3Xg64UtljMFYdfS30SVfBc',
  },
  alternates: {
    canonical: '/',
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
    <html lang="ja" className="dark">
      <body className={`${inter.variable} ${shippori.variable} font-sans min-h-screen bg-gray-950 text-white`}>
        <LangInit />
        <RateInit />
        <div className="flex flex-col min-h-screen">
          <Header />
          <main className="flex-1">{children}</main>
          <Footer />
        </div>
        <Toaster />
      </body>
    </html>
  )
}
// Trigger redeploy 2026-06-20-v3
