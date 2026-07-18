'use client'

import { useCallback, useEffect } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useAuthStore } from '@/store/auth'

export function useBackendAuth() {
  const { isSignedIn, isLoaded: isClerkLoaded } = useAuth()
  const {
    isAuthenticated,
    isLoading,
    hasHydrated,
    setHasHydrated,
    ensureBackendAuth,
    user,
    token,
  } = useAuthStore()

  useEffect(() => {
    if (hasHydrated) return
    const init = async () => {
      await useAuthStore.persist.rehydrate()
      setHasHydrated(true)
    }
    void init()
  }, [hasHydrated, setHasHydrated])

  useEffect(() => {
    if (!hasHydrated || !isClerkLoaded || !isSignedIn) return
    void ensureBackendAuth().catch(() => {})
  }, [hasHydrated, isClerkLoaded, isSignedIn, ensureBackendAuth])

  const isLoggedIn = Boolean(isSignedIn || isAuthenticated)
  const isReady = hasHydrated && isClerkLoaded

  const requireAuth = useCallback(async (): Promise<string | null> => {
    if (!isReady) return null
    if (!isSignedIn && !isAuthenticated) return null
    return ensureBackendAuth()
  }, [isReady, isSignedIn, isAuthenticated, ensureBackendAuth])

  return {
    user,
    token,
    isLoggedIn,
    isReady,
    isLoading,
    isSignedIn,
    isAuthenticated,
    requireAuth,
    ensureBackendAuth,
  }
}
