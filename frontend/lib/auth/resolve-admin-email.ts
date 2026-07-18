import type { NextRequest } from 'next/server'
import { auth, clerkClient, currentUser } from '@clerk/nextjs/server'
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

async function emailFromClerkUserId(userId: string): Promise<string | null> {
  try {
    const user = await clerkClient.users.getUser(userId)
    const email = (
      user.emailAddresses.find((e) => e.id === user.primaryEmailAddressId)?.emailAddress ||
      user.emailAddresses[0]?.emailAddress ||
      ''
    ).trim()
    return email ? email.toLowerCase() : null
  } catch {
    return null
  }
}

async function emailFromBearerToken(request: NextRequest): Promise<string | null> {
  const header = request.headers.get('authorization')
  if (!header?.startsWith('Bearer ')) return null

  const token = header.slice('Bearer '.length).trim()
  if (!token) return null

  const secretKey = process.env.CLERK_SECRET_KEY
  if (!secretKey) return null

  try {
    const { verifyToken } = await import('@clerk/backend')
    const payload = await verifyToken(token, { secretKey })

    const claimEmail = emailFromSessionClaims(payload as Record<string, unknown>)
    if (claimEmail) return claimEmail

    const userId = typeof payload.sub === 'string' ? payload.sub : null
    if (!userId) return null

    return emailFromClerkUserId(userId)
  } catch {
    return null
  }
}

/** Resolve the signed-in Clerk user's email when it matches ADMIN_EMAIL. */
export async function resolveAdminEmail(request?: NextRequest): Promise<string | null> {
  const authState = await auth()

  if (authState.userId) {
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

      if (isAdminEmail(email)) return email.toLowerCase()

      const fallbackEmail = await emailFromClerkUserId(authState.userId)
      if (fallbackEmail && isAdminEmail(fallbackEmail)) return fallbackEmail
    } catch {
      const fallbackEmail = await emailFromClerkUserId(authState.userId)
      if (fallbackEmail && isAdminEmail(fallbackEmail)) return fallbackEmail
    }
  }

  if (request) {
    const bearerEmail = await emailFromBearerToken(request)
    if (bearerEmail && isAdminEmail(bearerEmail)) {
      return bearerEmail
    }
  }

  return null
}
