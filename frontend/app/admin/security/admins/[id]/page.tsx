'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminSecurityApi } from '@/lib/api'
import type { AdminRole, AdminUserDetail } from '@/lib/types'
import { AdminSecurityNav } from '@/components/admin/AdminSecurityNav'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

export default function AdminSecurityAdminDetailPage() {
  const params = useParams()
  const router = useRouter()
  const id = Number(params.id)
  const { isReady } = useAdminGuard()
  const { hasPermission, readOnly } = useAdminPermissions()
  const [admin, setAdmin] = useState<AdminUserDetail | null>(null)
  const [roles, setRoles] = useState<AdminRole[]>([])
  const [roleCode, setRoleCode] = useState('')
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!isReady || !id) return
    Promise.all([adminSecurityApi.getAdmin(id), adminSecurityApi.listRoles()])
      .then(([adminRes, rolesRes]) => {
        setAdmin(adminRes.data)
        setRoleCode(adminRes.data.role.code)
        setRoles(rolesRes.data.filter((r) => r.code !== 'owner' || adminRes.data.role.code === 'owner'))
      })
      .catch(() => toast({ title: '管理者情報の取得に失敗しました', variant: 'destructive' }))
  }, [isReady, id])

  async function save() {
    if (!admin || readOnly || !hasPermission('admin.users.write')) return
    setSaving(true)
    try {
      const res = await adminSecurityApi.updateAdmin(admin.id, {
        role_code: roleCode !== admin.role.code ? roleCode : undefined,
        reason: reason || undefined,
      })
      setAdmin(res.data)
      toast({ title: '保存しました' })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast({
        title: '保存に失敗しました',
        description: typeof detail === 'string' ? detail : undefined,
        variant: 'destructive',
      })
    } finally {
      setSaving(false)
    }
  }

  async function toggleActive() {
    if (!admin || readOnly || !hasPermission('admin.users.write')) return
    setSaving(true)
    try {
      const res = await adminSecurityApi.updateAdmin(admin.id, {
        is_active: !admin.is_active,
        reason: reason || (admin.is_active ? '管理者無効化' : '管理者再有効化'),
      })
      setAdmin(res.data)
      toast({ title: admin.is_active ? '無効化しました' : '有効化しました' })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast({
        title: '操作に失敗しました',
        description: typeof detail === 'string' ? detail : undefined,
        variant: 'destructive',
      })
    } finally {
      setSaving(false)
    }
  }

  if (!isReady || !admin) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-2xl">
        <AdminSecurityNav title="管理者詳細" />
        <div className="space-y-4 rounded-xl border border-gray-200 p-6">
          <div>
            <p className="text-sm text-gray-500">メール</p>
            <p className="font-medium">{admin.email}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">名前</p>
            <p className="font-medium">{admin.display_name || admin.name}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">状態</p>
            <p className={admin.is_active ? 'text-green-600' : 'text-red-500'}>
              {admin.is_active ? '有効' : '無効'}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500 mb-2">付与権限</p>
            <ul className="text-sm text-gray-600 list-disc pl-5">
              {admin.permissions.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </div>
          {hasPermission('admin.users.write') && !readOnly && (
            <>
              <div>
                <Label htmlFor="role">役割</Label>
                <select
                  id="role"
                  value={roleCode}
                  onChange={(e) => setRoleCode(e.target.value)}
                  className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  disabled={admin.role.code === 'owner'}
                >
                  {roles.map((role) => (
                    <option key={role.code} value={role.code}>
                      {role.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Label htmlFor="reason">変更理由（任意）</Label>
                <Input id="reason" value={reason} onChange={(e) => setReason(e.target.value)} className="mt-1" />
              </div>
              <div className="flex gap-2">
                <Button onClick={save} disabled={saving || admin.role.code === 'owner'}>
                  保存
                </Button>
                <Button
                  variant="outline"
                  onClick={toggleActive}
                  disabled={saving || admin.role.code === 'owner'}
                >
                  {admin.is_active ? '無効化' : '有効化'}
                </Button>
                <Button variant="ghost" onClick={() => router.push('/admin/security/admins')}>
                  一覧へ
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
