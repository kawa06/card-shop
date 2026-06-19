import { Metadata } from 'next'

export const metadata: Metadata = {
  title: '注文履歴',
  robots: {
    index: false,
  },
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
