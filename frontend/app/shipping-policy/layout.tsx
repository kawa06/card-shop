import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: '配送ポリシー',
  description: 'KRX TCGの配送ポリシー。送料、発送方法、配送に関する注意事項を掲載しています。',
  alternates: {
    canonical: '/shipping-policy',
  },
}

export default function ShippingPolicyLayout({ children }: { children: React.ReactNode }) {
  return children
}
