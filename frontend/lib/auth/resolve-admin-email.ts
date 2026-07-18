import { auth, currentUser } from '@clerk/nextjs/server'
import { isAdminEmail } from '@/lib/auth/admin'

function emailFromSessionClaims(
  sessionClaims: Record<string, unknown> | null | undefined
): string | null {
  if (!sessionClaims) return null

  const candidates = [
    sessionClaims.email,
    sessionClaims.primary_email_address,
    sessionClaims.primaryEmailAddress,
  ]

  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate.trim().toLowerCase()
    }
  }

  return null
}

/** Resolve the signed-in Clerk user's email when it matches ADMIN_EMAIL. */
export async function resolveAdminEmail(): Promise<string | null> {
  const authState = await auth()
  if (!authState.userId) return null

  const claimEmail = emailFromSessionClaims(
    authState.sessionClaims as Record<string, unknown> | undefined
  )
  if (claimEmail && isAdminEmail(claimEmail)) {
    return claimEmail
  }

  try {
    const clerkUser = await currentUser()
    const email = (
      clerkUser?.emailAddresses.find((e) => e.id === clerkUser.primaryEmailAddressId)
        ?.emailAddress ||
      clerkUser?.emailAddresses[0]?.emailAddress ||
      ''
    ).trim()

    return isAdminEmail(email) ? email.toLowerCase() : null
  } catch {
    return null
  }
}
