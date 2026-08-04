'use client'

import Link from 'next/link'
import { LayoutDashboard } from 'lucide-react'
import { AdminNotificationBell } from '@/components/admin/AdminNotificationBell'

export function AdminChrome({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-white">
      <header className="sticky top-0 z-40 border-b border-gray-200 bg-white/95 backdrop-blur">
        <div className="container flex h-14 max-w-6xl items-center justify-between gap-4">
          <Link href="/admin" className="flex items-center gap-2 text-sm font-semibold text-gray-900 hover:text-yellow-600">
            <LayoutDashboard className="h-5 w-5 text-yellow-400" />
            管理画面
          </Link>
          <AdminNotificationBell />
        </div>
      </header>
      <main>{children}</main>
    </div>
  )
}
