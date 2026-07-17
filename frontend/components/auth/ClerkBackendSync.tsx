'use client'

import { useEffect, useRef } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useAuthStore } from '@/store/auth'

export function ClerkBackendSync() {
  const { isSignedIn, isLoaded } = useAuth()
  const { syncBackend, logout, token, hasHydrated, fetchMe } = useAuthStore()
  const didSyncRef = useRef(false)

  useEffect(() => {
    if (!isLoaded || !hasHydrated) return

    if (isSignedIn) {
      if (!didSyncRef.current) {
        didSyncRef.current = true
        syncBackend()
          .catch(() => fetchMe().catch(() => {}))
      } else if (token) {
        fetchMe().catch(() => {})
      }
      return
    }

    didSyncRef.current = false
    if (token) {
      logout()
    }
  }, [isLoaded, isSignedIn, token, hasHydrated, syncBackend, logout, fetchMe])

  return null
}
