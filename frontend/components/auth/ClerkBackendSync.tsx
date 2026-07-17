'use client'

import { useEffect, useRef } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useAuthStore } from '@/store/auth'

export function ClerkBackendSync() {
  const { isSignedIn, isLoaded } = useAuth()
  const { syncBackend, logout, token, hasHydrated, fetchMe } = useAuthStore()
  const syncAttemptsRef = useRef(0)

  useEffect(() => {
    if (!isLoaded || !hasHydrated) return

    if (!isSignedIn) {
      syncAttemptsRef.current = 0
      if (token) {
        logout()
      }
      return
    }

    if (!token) {
      if (syncAttemptsRef.current >= 5) return
      syncAttemptsRef.current += 1
      syncBackend().catch(() => {})
      return
    }

    syncAttemptsRef.current = 0
    fetchMe().catch(() => {})
  }, [isLoaded, isSignedIn, token, hasHydrated, syncBackend, logout, fetchMe])

  return null
}
