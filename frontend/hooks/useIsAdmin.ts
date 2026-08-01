'use client'

import { useAuth, useUser } from '@clerk/nextjs'
import { useAdminSessionStore } from '@/hooks/useAdminPermissions'

/** Server-validated admin session (not client-writable email checks). */
export function useIsAdmin(): boolean {
  const { userId, sessionId } = useAuth()
  const session = useAdminSessionStore((s) => s.session)
  const identity = useAdminSessionStore((s) => s.identity)
  const currentIdentity =
    userId && sessionId ? `${userId}:${sessionId}` : null
  return !!currentIdentity && identity === currentIdentity && !!session?.is_admin
}

export function useClerkEmail(): string | null {
  const { user: clerkUser } = useUser()
  if (!clerkUser) return null
  return (
    clerkUser.primaryEmailAddress?.emailAddress ||
    clerkUser.emailAddresses[0]?.emailAddress ||
    null
  )
}
