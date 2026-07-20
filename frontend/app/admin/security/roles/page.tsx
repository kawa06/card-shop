'use client'

import { useEffect, useState } from 'react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminSecurityApi } from '@/lib/api'
import type { AdminRole } from '@/lib/types'
import { AdminSecurityNav } from '@/components/admin/AdminSecurityNav'
import { toast } from '@/lib/use-toast'

export default function AdminSecurityRolesPage() {
  const { isReady } = useAdminGuard()
  const [roles, setRoles] = useState<AdminRole[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isReady) return
    adminSecurityApi
      .listRoles()
      .then((res) => setRoles(res.data))
      .catch(() => toast({ title: '役割一覧の取得に失敗しました', variant: 'destructive' }))
      .finally(() => setLoading(false))
  }, [isReady])

  if (!isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-3xl">
        <AdminSecurityNav title="役割設定" />
        <p className="text-sm text-gray-500 mb-4">
          システム定義の役割です。オーナー役割は通常の管理画面から追加できません。
        </p>
        <div className="rounded-xl border border-gray-200 overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-gray-400 animate-pulse">読み込み中...</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b border-gray-200 bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-gray-500">コード</th>
                  <th className="px-4 py-3 text-left text-gray-500">名称</th>
                  <th className="px-4 py-3 text-left text-gray-500">システム</th>
                </tr>
              </thead>
              <tbody>
                {roles.map((role) => (
                  <tr key={role.id} className="border-b border-gray-100">
                    <td className="px-4 py-3 font-mono text-xs">{role.code}</td>
                    <td className="px-4 py-3">{role.name}</td>
                    <td className="px-4 py-3">{role.is_system ? 'はい' : 'いいえ'}</td>
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
