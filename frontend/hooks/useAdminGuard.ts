'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@clerk/nextjs'
import { useAuthStore } from '@/store/auth'
import { useIsAdmin } from '@/hooks/useIsAdmin'

export function useAdminGuard() {
  const router = useRouter()
  const { isSignedIn, isLoaded: clerkLoaded } = useAuth()
  const { isAuthenticated, hasHydrated, syncBackend } = useAuthStore()
  const isAdmin = useIsAdmin()

  useEffect(() => {
    if (!hasHydrated || !clerkLoaded) return

    if (isSignedIn && !isAuthenticated) {
      syncBackend().catch(() => {})
    }

    if (!isSignedIn && !isAuthenticated) {
      router.push('/sign-in')
      return
    }

    if (!isAdmin) {
      router.push('/')
    }
  }, [hasHydrated, clerkLoaded, isSignedIn, isAuthenticated, isAdmin, router, syncBackend])

  const isReady = hasHydrated && clerkLoaded && (isSignedIn || isAuthenticated) && isAdmin
  return { isReady, isAdmin }
}
