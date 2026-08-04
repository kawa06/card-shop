import { Metadata } from 'next'
import { AdminGate } from './AdminGate'
import { AdminChrome } from '@/components/admin/AdminChrome'

export const metadata: Metadata = {
  title: '管理画面',
  robots: {
    index: false,
  },
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <AdminGate>
      <AdminChrome>{children}</AdminChrome>
    </AdminGate>
  )
}
