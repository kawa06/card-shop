import { Metadata } from 'next'
import HomeClient from './HomeClient'

export const metadata: Metadata = {
  title: 'KRX TCG | トレーディングカード販売サイト',
  description: 'ポケモンカード・ワンピースなど人気カードを取り扱う専門店。最新のカードからレアなアイテムまで豊富に取り揃えています。',
  openGraph: {
    title: 'KRX TCG | トレーディングカード販売サイト',
    description: 'ポケモンカード・ワンピースなど人気カードを取り扱う専門店',
    images: ['/ogp.png'],
  },
}

export default function HomePage() {
  return <HomeClient />
}