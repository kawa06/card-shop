'use client'

import { useEffect } from 'react'
import { useAuth } from '@clerk/nextjs'
import { useAdminSessionStore } from '@/hooks/useAdminPermissions'

/**
 * Owns the application-wide, server-validated admin session lifecycle.
 * Clerk identifies the session; only the admin API response grants privileges.
 */
export function AdminSessionSync() {
  const { isLoaded, isSignedIn, userId, sessionId } = useAuth()
  const loginSession = useAdminSessionStore((state) => state.loginSession)
  const loadSession = useAdminSessionStore((state) => state.loadSession)
  const setIdentity = useAdminSessionStore((state) => state.setIdentity)
  const clearSession = useAdminSessionStore((state) => state.clearSession)

  useEffect(() => {
    if (!isLoaded) return

    if (!isSignedIn || !userId || !sessionId) {
      clearSession()
      return
    }

    setIdentity(`${userId}:${sessionId}`)
    void loginSession()
  }, [
    clearSession,
    isLoaded,
    isSignedIn,
    loginSession,
    sessionId,
    setIdentity,
    userId,
  ])

  useEffect(() => {
    if (!isLoaded || !isSignedIn || !userId || !sessionId) return

    const refresh = () => {
      void loadSession()
    }
    const refreshWhenVisible = () => {
      if (document.visibilityState === 'visible') refresh()
    }

    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', refreshWhenVisible)
    return () => {
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', refreshWhenVisible)
    }
  }, [isLoaded, isSignedIn, loadSession, sessionId, userId])

  return null
}
