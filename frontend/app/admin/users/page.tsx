'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { ArrowLeft, Shield } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminApi } from '@/lib/api'
import { User } from '@/lib/types'
import { Button } from '@/components/ui/button'

export default function AdminUsersPage() {
  const { isReady } = useAdminGuard()
  const [users, setUsers] = useState<User[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  useEffect(() => {
    if (!isMounted || !isReady) return
    
    adminApi.getAllUsers().then(res => {
      setUsers(res.data || [])
    }).catch(() => {}).finally(() => setIsLoading(false))
  }, [isMounted, isReady])

  if (!isMounted || !isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-4xl">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/admin">
            <Button variant="ghost" size="icon" className="text-gray-400 hover:text-gray-900">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">ユーザー管理</h1>
        </div>

        <div className="bg-gray-50 rounded-xl border border-gray-200 overflow-hidden">
          {isLoading ? (
            <div className="p-8 text-center text-gray-400 animate-pulse">読み込み中...</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-gray-200">
                  <tr>
                    <th className="text-left text-gray-400 font-medium px-4 py-3">名前</th>
                    <th className="text-left text-gray-400 font-medium px-4 py-3">メール</th>
                    <th className="text-left text-gray-400 font-medium px-4 py-3">権限</th>
                    <th className="text-left text-gray-400 font-medium px-4 py-3">登録日</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b border-gray-100 hover:bg-gray-100">
                      <td className="px-4 py-3 text-gray-900">{u.name}</td>
                      <td className="px-4 py-3 text-gray-400">{u.email}</td>
                      <td className="px-4 py-3">
                        {u.is_admin ? (
                          <span className="flex items-center gap-1 text-yellow-400 text-xs font-medium">
                            <Shield className="h-3 w-3" />
                            管理者
                          </span>
                        ) : (
                          <span className="text-gray-500 text-xs">一般ユーザー</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {new Date(u.created_at).toLocaleDateString('ja-JP')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
