'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'
import { useAuthStore } from '@/store/auth'
import { useIsAdmin } from '@/hooks/useIsAdmin'

export function useAdminGuard() {
  const router = useRouter()
  const { isSignedIn, isLoaded: clerkLoaded } = useAuth()
  const { hasHydrated, token, authProvider, ensureBackendAuth } = useAuthStore()
  const isAdmin = useIsAdmin()
  const [sessionReady, setSessionReady] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [syncError, setSyncError] = useState<string | null>(null)

  const ensureSession = useCallback(async () => {
    if (!hasHydrated || !clerkLoaded) return

    if (!isSignedIn && authProvider !== 'legacy') {
      router.push('/sign-in')
      return
    }

    if (!isAdmin) {
      router.push('/')
      return
    }

    setIsSyncing(true)
    setSyncError(null)
    try {
      const validToken = isSignedIn
        ? await ensureBackendAuth()
        : await ensureBackendAuth({ force: !token })

      if (!validToken) {
        throw new Error('バックエンド認証の同期に失敗しました')
      }

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
  }, [hasHydrated, clerkLoaded, isSignedIn, isAdmin, token, authProvider, router, ensureBackendAuth])

  useEffect(() => {
    ensureSession()
  }, [ensureSession])

  const retrySync = useCallback(async () => {
    setIsSyncing(true)
    setSyncError(null)
    try {
      const valid = await ensureBackendAuth({ force: true })
      if (!valid) {
        throw new Error('バックエンド認証の同期に失敗しました')
      }
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
  }, [ensureBackendAuth])

  const isReady =
    hasHydrated &&
    clerkLoaded &&
    isAdmin &&
    sessionReady &&
    !!token &&
    (isSignedIn || authProvider === 'legacy')

  return { isReady, isAdmin, isSyncing, syncError, retrySync }
}
