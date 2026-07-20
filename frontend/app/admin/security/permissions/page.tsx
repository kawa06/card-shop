'use client'

import { useEffect, useState } from 'react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminSecurityApi } from '@/lib/api'
import type { AdminPermissionsMatrix } from '@/lib/types'
import { AdminSecurityNav } from '@/components/admin/AdminSecurityNav'
import { toast } from '@/lib/use-toast'

export default function AdminSecurityPermissionsPage() {
  const { isReady } = useAdminGuard()
  const [matrix, setMatrix] = useState<AdminPermissionsMatrix | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isReady) return
    adminSecurityApi
      .getPermissionsMatrix()
      .then((res) => setMatrix(res.data))
      .catch(() => toast({ title: '権限マトリクスの取得に失敗しました', variant: 'destructive' }))
      .finally(() => setLoading(false))
  }, [isReady])

  if (!isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-6xl">
        <AdminSecurityNav title="権限確認" />
        {loading || !matrix ? (
          <div className="p-8 text-center text-gray-400 animate-pulse">読み込み中...</div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-gray-200">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-3 py-2 text-left text-gray-500 sticky left-0 bg-gray-50">権限</th>
                  {matrix.roles.map((role) => (
                    <th key={role.code} className="px-3 py-2 text-left text-gray-500 whitespace-nowrap">
                      {role.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {matrix.permissions.map((perm) => (
                  <tr key={perm.code} className="border-b border-gray-100">
                    <td className="px-3 py-2 font-mono sticky left-0 bg-white">{perm.code}</td>
                    {matrix.roles.map((role) => (
                      <td key={role.code} className="px-3 py-2 text-center">
                        {matrix.role_permissions[role.code]?.includes(perm.code) ? '✓' : '—'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
