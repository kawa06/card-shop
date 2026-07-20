'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const NAV = [
  { href: '/admin/security/admins', label: '管理者一覧' },
  { href: '/admin/security/admins/new', label: '管理者追加' },
  { href: '/admin/security/roles', label: '役割設定' },
  { href: '/admin/security/permissions', label: '権限確認' },
  { href: '/admin/security/audit-logs', label: '監査ログ' },
]

export function AdminSecurityNav({ title }: { title: string }) {
  const pathname = usePathname()

  return (
    <div className="mb-6 space-y-4">
      <div className="flex items-center gap-3">
        <Link href="/admin">
          <Button variant="ghost" size="icon" className="text-gray-400 hover:text-gray-900">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
      </div>
      <nav className="flex flex-wrap gap-2">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              'rounded-lg border px-3 py-1.5 text-sm transition-colors',
              pathname === item.href || pathname.startsWith(item.href + '/')
                ? 'border-yellow-400 bg-yellow-400/10 text-gray-900'
                : 'border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-900'
            )}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </div>
  )
}
