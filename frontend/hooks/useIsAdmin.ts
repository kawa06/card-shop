'use client'

import { useUser } from '@clerk/nextjs'
import { useAuthStore } from '@/store/auth'
import { isAdminEmail } from '@/lib/auth/admin'

export function useClerkEmail(): string | null {
  const { user: clerkUser } = useUser()
  if (!clerkUser) return null
  return (
    clerkUser.primaryEmailAddress?.emailAddress ||
    clerkUser.emailAddresses[0]?.emailAddress ||
    null
  )
}

/** Clerk メールまたはバックエンド user.is_admin のどちらかで管理者判定 */
export function useIsAdmin(): boolean {
  const clerkEmail = useClerkEmail()
  const { user } = useAuthStore()
  return !!(user?.is_admin || isAdminEmail(clerkEmail))
}
