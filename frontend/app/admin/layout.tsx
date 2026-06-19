import { Metadata } from 'next'

export const metadata: Metadata = {
  title: '管理画面',
  robots: {
    index: false,
  },
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
