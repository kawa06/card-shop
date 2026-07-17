'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'
import { useIsAdmin } from '@/hooks/useIsAdmin'

export function useAdminGuard() {
  const router = useRouter()
  const { isSignedIn, isLoaded: clerkLoaded } = useAuth()
  const isAdmin = useIsAdmin()
  const [checked, setChecked] = useState(false)

  const checkAccess = useCallback(() => {
    if (!clerkLoaded) return

    if (!isSignedIn) {
      router.push('/sign-in')
      return
    }

    if (!isAdmin) {
      router.push('/')
      return
    }

    setChecked(true)
  }, [clerkLoaded, isSignedIn, isAdmin, router])

  useEffect(() => {
    checkAccess()
  }, [checkAccess])

  const isReady = clerkLoaded && isSignedIn && isAdmin && checked

  return { isReady, isAdmin, isSyncing: !isReady && clerkLoaded, syncError: null, retrySync: checkAccess }
}
