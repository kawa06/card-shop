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
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<void>
  logout: () => void
  fetchMe: () => Promise<void>
}

async function fetchBackendSession(): Promise<{ access_token: string; user: User } | null> {
  const res = await fetch('/api/auth/backend-sync', { method: 'POST' })
  if (!res.ok) return null
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
        set({ isLoading: true })
        try {
          const synced = await fetchBackendSession()
          if (!synced) {
            throw new Error('バックエンドとの同期に失敗しました')
          }
          applyBackendSession(set, synced.access_token, synced.user, 'clerk')
        } catch (error) {
          set({ isLoading: false })
          throw error
        }
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
