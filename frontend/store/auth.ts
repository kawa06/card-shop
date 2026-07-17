'use client'

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { User } from '@/lib/types'
import { authApi } from '@/lib/api'
import { useFavoritesStore } from '@/store/favorites'

interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean
  hasHydrated: boolean
  authProvider: 'clerk' | 'legacy' | null
  setHasHydrated: (state: boolean) => void
  syncBackend: () => Promise<void>
  clearBackendToken: () => void
  validateBackendToken: () => Promise<boolean>
  ensureBackendAuth: (options?: { force?: boolean }) => Promise<string | null>
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<void>
  logout: () => void
  fetchMe: () => Promise<void>
}

async function fetchBackendSession(): Promise<{ access_token: string; user: User }> {
  const res = await fetch('/api/auth/backend-sync', {
    method: 'POST',
    credentials: 'same-origin',
  })
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

      clearBackendToken: () => {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('auth_token')
        }
        set({
          token: null,
          user: null,
          isAuthenticated: false,
          isLoading: false,
        })
      },

      validateBackendToken: async () => {
        const token =
          get().token ||
          (typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null)
        if (!token) return false

        if (typeof window !== 'undefined' && token !== localStorage.getItem('auth_token')) {
          localStorage.setItem('auth_token', token)
        }

        try {
          const res = await fetch('/api/auth/me', {
            headers: { Authorization: `Bearer ${token}` },
          })
          if (!res.ok) {
            if (res.status === 401) {
              get().clearBackendToken()
            }
            return false
          }
          const user = (await res.json()) as User
          set({ user, isAuthenticated: true, token })
          return true
        } catch {
          return false
        }
      },

      ensureBackendAuth: async (options?: { force?: boolean }) => {
        if (options?.force) {
          get().clearBackendToken()
        } else {
          const valid = await get().validateBackendToken()
          if (valid) return get().token
        }

        // Legacy login cannot auto-sync via Clerk; caller should redirect to sign-in.
        if (get().authProvider === 'legacy') {
          return null
        }

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
        useFavoritesStore.getState().reset()
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
          if (status === 401) {
            if (get().authProvider === 'clerk') {
              get().clearBackendToken()
              await get().syncBackend().catch(() => {})
            } else {
              get().logout()
            }
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
