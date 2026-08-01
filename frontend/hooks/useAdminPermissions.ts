'use client'

import { create } from 'zustand'
import type { AdminSession } from '@/lib/types'
import { getClerkSessionToken } from '@/lib/clerk-token'
import {
  classifyAdminSessionFailure,
  type AdminSessionFailure,
} from '@/lib/auth/admin-session-state'

export type AdminSessionStatus =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'transient'
  | 'unauthenticated'
  | 'forbidden'
  | 'error'

interface AdminSessionState {
  session: AdminSession | null
  loaded: boolean
  status: AdminSessionStatus
  identity: string | null
  loadSession: () => Promise<AdminSession | null>
  loginSession: () => Promise<AdminSession | null>
  setIdentity: (identity: string) => void
  clearSession: () => void
  hasPermission: (code: string) => boolean
}

class AdminSessionRequestError extends Error {
  constructor(public readonly status: number | null) {
    super('Admin session request failed')
  }
}

let requestGeneration = 0
let inFlight: Promise<AdminSession | null> | null = null

function isAdminSession(value: unknown): value is AdminSession {
  if (!value || typeof value !== 'object') return false
  const session = value as Partial<AdminSession>
  return (
    typeof session.is_admin === 'boolean' &&
    Array.isArray(session.permissions) &&
    session.permissions.every((permission) => typeof permission === 'string') &&
    typeof session.reauth_valid === 'boolean'
  )
}

async function requestSession(path: string, method: 'GET' | 'POST', forceToken = false) {
  const token = await getClerkSessionToken(forceToken)
  let response: Response

  try {
    response = await fetch(path, {
      method,
      credentials: 'same-origin',
      cache: 'no-store',
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    })
  } catch {
    throw new AdminSessionRequestError(null)
  }

  if (!response.ok) {
    throw new AdminSessionRequestError(response.status)
  }

  const data: unknown = await response.json().catch(() => null)
  if (!isAdminSession(data)) {
    throw new AdminSessionRequestError(response.status)
  }
  return data
}

async function synchronizeSession(
  path: string,
  method: 'GET' | 'POST',
  set: (partial: Partial<AdminSessionState>) => void,
  get: () => AdminSessionState
): Promise<AdminSession | null> {
  if (inFlight) return inFlight

  const generation = requestGeneration
  set({ status: 'loading' })

  const request = (async () => {
    try {
      let session: AdminSession
      try {
        session = await requestSession(path, method)
      } catch (error) {
        if (!(error instanceof AdminSessionRequestError) || error.status !== 401) {
          throw error
        }
        // A stale Clerk token is recoverable once. The retry must bypass Clerk's cache.
        session = await requestSession(path, method, true)
      }

      if (generation !== requestGeneration) return null
      set({ session, loaded: true, status: 'ready' })
      return session
    } catch (error) {
      if (generation !== requestGeneration) return null
      const failure: AdminSessionFailure =
        error instanceof AdminSessionRequestError
          ? classifyAdminSessionFailure(error.status)
          : 'transient'

      if (failure === 'transient') {
        // Keep the last server-verified privileges only for network and 5xx failures.
        set({ loaded: true, status: 'transient' })
      } else {
        set({ session: null, loaded: true, status: failure })
      }
      return null
    }
  })()

  inFlight = request
  try {
    return await request
  } finally {
    if (inFlight === request) inFlight = null
  }
}

export const useAdminSessionStore = create<AdminSessionState>((set, get) => ({
  session: null,
  loaded: false,
  status: 'idle',
  identity: null,
  loadSession: () =>
    synchronizeSession('/api/admin/security/me', 'GET', set, get),
  loginSession: () =>
    synchronizeSession('/api/admin/security/session/login', 'POST', set, get),
  setIdentity: (identity) => {
    if (get().identity !== identity) {
      requestGeneration += 1
      inFlight = null
      set({
        identity,
        session: null,
        loaded: false,
        status: 'idle',
      })
    }
  },
  clearSession: () => {
    requestGeneration += 1
    inFlight = null
    set({
      session: null,
      loaded: false,
      status: 'idle',
      identity: null,
    })
  },
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
