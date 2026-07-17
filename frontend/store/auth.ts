'use client'

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { User } from '@/lib/types'
import { authApi } from '@/lib/api'

interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean
  hasHydrated: boolean
  authProvider: 'clerk' | 'legacy' | null
  setHasHydrated: (state: boolean) => void
  syncBackend: () => Promise<void>
  ensureBackendAuth: () => Promise<string | null>
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<void>
  logout: () => void
  fetchMe: () => Promise<void>
}

async function fetchBackendSession(): Promise<{ access_token: string; user: User }> {
  const res = await fetch('/api/auth/backend-sync', { method: 'POST' })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail =
      typeof body.detail === 'string' && body.detail.trim()
        ? body.detail
        : 'バックエンドとの同期に失敗しました'
    throw new Error(detail)
  }
  return res.json()
}

function applyBackendSession(
  set: (partial: Partial<AuthState>) => void,
  access_token: string,
  user: User,
  authProvider: 'clerk' | 'legacy'
) {
  if (typeof window !== 'undefined') {
    localStorage.setItem('auth_token', access_token)
  }
  set({
    token: access_token,
    user,
    isAuthenticated: true,
    isLoading: false,
    hasHydrated: true,
    authProvider,
  })
}

let syncInFlight: Promise<void> | null = null

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isLoading: false,
      isAuthenticated: false,
      hasHydrated: false,
      authProvider: null,

      setHasHydrated: (state: boolean) => {
        set({ hasHydrated: state })
      },

      syncBackend: async () => {
        if (syncInFlight) return syncInFlight
        syncInFlight = (async () => {
          set({ isLoading: true })
          try {
            const synced = await fetchBackendSession()
            applyBackendSession(set, synced.access_token, synced.user, 'clerk')
          } catch (error) {
            set({ isLoading: false })
            throw error
          }
        })().finally(() => {
          syncInFlight = null
        })
        return syncInFlight
      },

      ensureBackendAuth: async () => {
        const { token, isAuthenticated } = get()
        if (token && isAuthenticated) return token
        await get().syncBackend()
        return get().token
      },

      login: async (email: string, password: string) => {
        await useAuthStore.persist.rehydrate()
        set({ isLoading: true })
        try {
          const res = await authApi.login({ email, password })
          const { access_token, user } = res.data
          applyBackendSession(set, access_token, user, 'legacy')
        } catch (error) {
          set({ isLoading: false })
          throw error
        }
      },

      register: async (email: string, password: string, name: string) => {
        set({ isLoading: true })
        try {
          const res = await authApi.register({ email, password, name })
          const { access_token, user } = res.data
          applyBackendSession(set, access_token, user, 'legacy')
        } catch (error) {
          set({ isLoading: false })
          throw error
        }
      },

      logout: () => {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('auth_token')
        }
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          authProvider: null,
        })
      },

      fetchMe: async () => {
        const token = get().token
        if (!token) return
        try {
          const res = await authApi.me()
          set({ user: res.data, isAuthenticated: true })
        } catch (error: unknown) {
          const status = (error as { response?: { status?: number } })?.response?.status
          // Clerkログイン中は一時的な401でログアウトしない
          if (status === 401 && get().authProvider !== 'clerk') {
            get().logout()
          }
        }
      },
    }),
    {
      name: 'auth-storage',
      version: 3,
      skipHydration: true,
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
        authProvider: state.authProvider,
      }),
    }
  )
)
