import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: '利用規約',
  description: 'KRX TCGの利用規約。サービスのご利用条件について定めています。',
  alternates: {
    canonical: '/terms',
  },
}

export default function TermsLayout({ children }: { children: React.ReactNode }) {
  return children
}
