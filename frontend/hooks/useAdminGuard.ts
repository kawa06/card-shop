'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'
import { useAdminSessionStore } from '@/hooks/useAdminPermissions'

export function useAdminGuard() {
  const router = useRouter()
  const { isSignedIn, isLoaded: clerkLoaded } = useAuth()
  const loginSession = useAdminSessionStore((s) => s.loginSession)
  const session = useAdminSessionStore((s) => s.session)
  const loaded = useAdminSessionStore((s) => s.loaded)
  const [checked, setChecked] = useState(false)

  const checkAccess = useCallback(async () => {
    if (!clerkLoaded) return

    if (!isSignedIn) {
      router.push('/sign-in')
      return
    }

    const result = await loginSession()
    if (!result?.is_admin) {
      router.push('/')
      return
    }

    setChecked(true)
  }, [clerkLoaded, isSignedIn, loginSession, router])

  useEffect(() => {
    checkAccess()
  }, [checkAccess])

  const isReady = clerkLoaded && isSignedIn && !!session?.is_admin && checked

  return {
    isReady,
    isAdmin: !!session?.is_admin,
    isSyncing: !isReady && clerkLoaded,
    syncError: null,
    retrySync: checkAccess,
    session,
  }
}
