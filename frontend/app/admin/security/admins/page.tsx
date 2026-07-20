'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminSecurityApi } from '@/lib/api'
import type { AdminUserSummary } from '@/lib/types'
import { AdminSecurityNav } from '@/components/admin/AdminSecurityNav'
import { Button } from '@/components/ui/button'
import { toast } from '@/lib/use-toast'

export default function AdminSecurityAdminsPage() {
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const [items, setItems] = useState<AdminUserSummary[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isReady) return
    adminSecurityApi
      .listAdmins()
      .then((res) => setItems(res.data.items))
      .catch(() => {
        toast({ title: '管理者一覧の取得に失敗しました', variant: 'destructive' })
      })
      .finally(() => setLoading(false))
  }, [isReady])

  if (!isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-5xl">
        <AdminSecurityNav title="管理者一覧" />
        {hasPermission('admin.users.write') && (
          <div className="mb-4">
            <Link href="/admin/security/admins/new">
              <Button>管理者を追加</Button>
            </Link>
          </div>
        )}
        <div className="rounded-xl border border-gray-200 overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-gray-400 animate-pulse">読み込み中...</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b border-gray-200 bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-gray-500">名前</th>
                  <th className="px-4 py-3 text-left text-gray-500">メール</th>
                  <th className="px-4 py-3 text-left text-gray-500">役割</th>
                  <th className="px-4 py-3 text-left text-gray-500">状態</th>
                  <th className="px-4 py-3 text-left text-gray-500">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-b border-gray-100">
                    <td className="px-4 py-3">{item.display_name || item.name}</td>
                    <td className="px-4 py-3 text-gray-500">{item.email}</td>
                    <td className="px-4 py-3">{item.role.name}</td>
                    <td className="px-4 py-3">
                      {item.is_active ? (
                        <span className="text-green-600">有効</span>
                      ) : (
                        <span className="text-red-500">無効</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Link href={`/admin/security/admins/${item.id}`} className="text-yellow-600 hover:underline">
                        詳細
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
