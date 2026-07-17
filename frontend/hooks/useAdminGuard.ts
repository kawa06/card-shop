'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'
import { useAuthStore } from '@/store/auth'
import { useIsAdmin } from '@/hooks/useIsAdmin'

export function useAdminGuard() {
  const router = useRouter()
  const { isSignedIn, isLoaded: clerkLoaded } = useAuth()
  const { isAuthenticated, hasHydrated, syncBackend, token, authProvider } = useAuthStore()
  const isAdmin = useIsAdmin()
  const [sessionReady, setSessionReady] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [syncError, setSyncError] = useState<string | null>(null)

  const ensureSession = useCallback(async () => {
    if (!hasHydrated || !clerkLoaded) return

    if (!isSignedIn && !isAuthenticated) {
      router.push('/sign-in')
      return
    }

    if (!isAdmin) {
      router.push('/')
      return
    }

    if (token && isAuthenticated) {
      setSessionReady(true)
      setSyncError(null)
      return
    }

    if (!isSignedIn) {
      setSessionReady(!!token)
      return
    }

    setIsSyncing(true)
    setSyncError(null)
    try {
      await syncBackend()
      setSessionReady(true)
    } catch (err) {
      setSessionReady(false)
      setSyncError(
        err instanceof Error
          ? err.message
          : 'バックエンド認証の同期に失敗しました。ページを再読み込みしてください。'
      )
    } finally {
      setIsSyncing(false)
    }
  }, [
    hasHydrated,
    clerkLoaded,
    isSignedIn,
    isAuthenticated,
    isAdmin,
    token,
    router,
    syncBackend,
  ])

  useEffect(() => {
    ensureSession()
  }, [ensureSession])

  const retrySync = useCallback(async () => {
    setIsSyncing(true)
    setSyncError(null)
    try {
      await syncBackend()
      setSessionReady(true)
    } catch (err) {
      setSessionReady(false)
      setSyncError(
        err instanceof Error
          ? err.message
          : 'バックエンド認証の同期に失敗しました。'
      )
    } finally {
      setIsSyncing(false)
    }
  }, [syncBackend])

  const isReady =
    hasHydrated &&
    clerkLoaded &&
    isAdmin &&
    sessionReady &&
    !!token &&
    (isSignedIn || isAuthenticated || authProvider === 'legacy')

  return { isReady, isAdmin, isSyncing, syncError, retrySync }
}
