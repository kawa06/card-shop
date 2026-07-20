'use client'

import { FormEvent, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminSecurityApi } from '@/lib/api'
import type { AdminRole } from '@/lib/types'
import { AdminSecurityNav } from '@/components/admin/AdminSecurityNav'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

export default function AdminSecurityNewAdminPage() {
  const router = useRouter()
  const { isReady } = useAdminGuard()
  const { hasPermission, readOnly } = useAdminPermissions()
  const [roles, setRoles] = useState<AdminRole[]>([])
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!isReady) return
    if (!hasPermission('admin.users.write')) {
      router.replace('/admin/security/admins')
      return
    }
    adminSecurityApi.listRoles().then((res) => {
      setRoles(res.data.filter((r) => r.code !== 'owner'))
    })
  }, [isReady, hasPermission, router])

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (readOnly) return
    const form = new FormData(e.currentTarget)
    setSubmitting(true)
    try {
      const res = await adminSecurityApi.createAdmin({
        email: String(form.get('email') || ''),
        name: String(form.get('name') || ''),
        role_code: String(form.get('role_code') || 'viewer'),
        display_name: String(form.get('display_name') || '') || undefined,
      })
      toast({ title: '管理者を追加しました' })
      router.push(`/admin/security/admins/${res.data.id}`)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast({
        title: '追加に失敗しました',
        description: typeof detail === 'string' ? detail : undefined,
        variant: 'destructive',
      })
    } finally {
      setSubmitting(false)
    }
  }

  if (!isReady || readOnly) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-xl">
        <AdminSecurityNav title="管理者追加" />
        <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-gray-200 p-6">
          <div>
            <Label htmlFor="email">メールアドレス</Label>
            <Input id="email" name="email" type="email" required className="mt-1" />
          </div>
          <div>
            <Label htmlFor="name">名前</Label>
            <Input id="name" name="name" required className="mt-1" />
          </div>
          <div>
            <Label htmlFor="display_name">表示名（任意）</Label>
            <Input id="display_name" name="display_name" className="mt-1" />
          </div>
          <div>
            <Label htmlFor="role_code">役割</Label>
            <select
              id="role_code"
              name="role_code"
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              defaultValue="viewer"
            >
              {roles.map((role) => (
                <option key={role.code} value={role.code}>
                  {role.name}
                </option>
              ))}
            </select>
          </div>
          <Button type="submit" disabled={submitting}>
            {submitting ? '追加中...' : '管理者を追加'}
          </Button>
        </form>
      </div>
    </div>
  )
}
