'use client'

import { create } from 'zustand'
import type { AdminSession } from '@/lib/types'
import { adminSecurityApi } from '@/lib/api'

interface AdminSessionState {
  session: AdminSession | null
  loaded: boolean
  loadSession: () => Promise<AdminSession | null>
  loginSession: () => Promise<AdminSession | null>
  clearSession: () => void
  hasPermission: (code: string) => boolean
}

export const useAdminSessionStore = create<AdminSessionState>((set, get) => ({
  session: null,
  loaded: false,
  loadSession: async () => {
    try {
      const res = await adminSecurityApi.getSession()
      set({ session: res.data, loaded: true })
      return res.data
    } catch {
      set({ session: { is_admin: false, permissions: [], reauth_valid: false }, loaded: true })
      return null
    }
  },
  loginSession: async () => {
    try {
      const res = await adminSecurityApi.sessionLogin()
      set({ session: res.data, loaded: true })
      return res.data
    } catch {
      try {
        await adminSecurityApi.reportLoginFailed('client_guard_rejected')
      } catch {
        /* ignore */
      }
      set({ session: { is_admin: false, permissions: [], reauth_valid: false }, loaded: true })
      return null
    }
  },
  clearSession: () => set({ session: null, loaded: false }),
  hasPermission: (code: string) => {
    const perms = get().session?.permissions ?? []
    return perms.includes(code)
  },
}))

export function useAdminPermissions() {
  const session = useAdminSessionStore((s) => s.session)
  const hasPermission = useAdminSessionStore((s) => s.hasPermission)
  const canWrite = hasPermission('admin.users.write')
  const isViewer = session?.role_code === 'viewer'
  return {
    session,
    permissions: session?.permissions ?? [],
    hasPermission,
    canWrite,
    isViewer,
    readOnly: isViewer || !canWrite,
  }
}
