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
  setHasHydrated: (state: boolean) => void
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<void>
  logout: () => void
  fetchMe: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isLoading: false,
      isAuthenticated: false,
      hasHydrated: false,

      setHasHydrated: (state: boolean) => {
        set({ hasHydrated: state })
      },

      login: async (email: string, password: string) => {
        await useAuthStore.persist.rehydrate()
        set({ isLoading: true })
        try {
          const res = await authApi.login({ email, password })
          const { access_token, user } = res.data
          if (typeof window !== 'undefined') {
            localStorage.setItem('auth_token', access_token)
          }
          set({ token: access_token, user, isAuthenticated: true, isLoading: false, hasHydrated: true })
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
          if (typeof window !== 'undefined') {
            localStorage.setItem('auth_token', access_token)
          }
          set({ token: access_token, user, isAuthenticated: true, isLoading: false })
        } catch (error) {
          set({ isLoading: false })
          throw error
        }
      },

      logout: () => {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('auth_token')
        }
        set({ user: null, token: null, isAuthenticated: false })
      },

      fetchMe: async () => {
        const token = get().token
        if (!token) return
        try {
          const res = await authApi.me()
          set({ user: res.data, isAuthenticated: true })
        } catch (error: any) {
          if (error.response?.status === 401) {
            get().logout()
          }
        }
      },
    }),
    {
      name: 'auth-storage',
      version: 1,
      skipHydration: true,
      partialize: (state) => ({ token: state.token, user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
)
