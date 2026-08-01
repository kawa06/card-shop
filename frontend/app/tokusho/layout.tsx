import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: '特定商取引法に基づく表記',
  description: 'KRX TCGの特定商取引法に基づく表記。販売事業者情報、支払方法、返品ポリシーなどを掲載しています。',
  alternates: {
    canonical: '/tokusho',
  },
}

export default function TokushoLayout({ children }: { children: React.ReactNode }) {
  return children
}
