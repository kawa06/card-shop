import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import Header from '@/components/layout/Header'
import Footer from '@/components/layout/Footer'
import { Toaster } from '@/components/ui/toaster'
import { LangInit } from '@/components/LangInit'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Oripa_kawa - トレーディングカード専門店',
  description: 'レアカードから初心者向けカードまで豊富なラインナップのトレーディングカード専門店',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ja" className="dark">
      <body className={`${inter.className} min-h-screen bg-gray-950 text-white`}>
        <LangInit />
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
