'use client'

import { useEffect } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useAuthStore } from '@/store/auth'

export function ClerkBackendSync() {
  const { isSignedIn, isLoaded } = useAuth()
  const { syncBackend, logout, token, hasHydrated, fetchMe, ensureBackendAuth } = useAuthStore()

  useEffect(() => {
    if (!isLoaded || !hasHydrated) return

    if (!isSignedIn) {
      if (token) {
        logout()
      }
      return
    }

    if (!token) {
      void syncBackend().catch(() => {})
      return
    }

    void fetchMe().catch(async () => {
      await ensureBackendAuth({ force: true }).catch(() => {})
    })
  }, [isLoaded, isSignedIn, token, hasHydrated, syncBackend, logout, fetchMe, ensureBackendAuth])

  return null
}
