'use client'

import { useCallback, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'
import { useAdminSessionStore } from '@/hooks/useAdminPermissions'

export function useAdminGuard() {
  const router = useRouter()
  const { isSignedIn, isLoaded: clerkLoaded, userId, sessionId } = useAuth()
  const loginSession = useAdminSessionStore((s) => s.loginSession)
  const session = useAdminSessionStore((s) => s.session)
  const status = useAdminSessionStore((s) => s.status)
  const identity = useAdminSessionStore((s) => s.identity)

  const checkAccess = useCallback(async () => {
    if (!clerkLoaded || !isSignedIn) return
    await loginSession()
  }, [clerkLoaded, isSignedIn, loginSession])

  useEffect(() => {
    if (!clerkLoaded) return
    if (!isSignedIn || status === 'unauthenticated') {
      router.push('/sign-in')
      return
    }
    if (status === 'forbidden' || (status === 'ready' && !session?.is_admin)) {
      router.push('/')
    }
  }, [clerkLoaded, isSignedIn, router, session?.is_admin, status])

  const currentIdentity =
    userId && sessionId ? `${userId}:${sessionId}` : null
  const identityMatches = !!currentIdentity && identity === currentIdentity
  const canUseVerifiedSession =
    status === 'ready' || status === 'loading' || status === 'transient'
  const isReady =
    clerkLoaded &&
    !!isSignedIn &&
    identityMatches &&
    canUseVerifiedSession &&
    !!session?.is_admin

  return {
    isReady,
    isAdmin: identityMatches && !!session?.is_admin,
    isSyncing: status === 'idle' || status === 'loading',
    syncError:
      status === 'transient'
        ? '管理者セッションを更新できませんでした。接続回復後に再試行します。'
        : status === 'error'
          ? '管理者セッションを確認できませんでした。'
          : null,
    retrySync: checkAccess,
    session,
    status,
  }
}
