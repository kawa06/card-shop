import type { NextRequest } from 'next/server'
import { auth, clerkClient, currentUser } from '@clerk/nextjs/server'
import type { AdminSession } from '@/lib/types'
import { adminProxyHeaders } from '@/lib/auth/admin-proxy-signature'

function getBackendUrl() {
  return (
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.API_URL ||
    'https://backend-production-054e.up.railway.app'
  ).replace(/\/$/, '')
}

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

async function resolveClerkEmail(request?: NextRequest): Promise<string | null> {
  const authState = await auth()

  if (authState.userId) {
    const claimEmail = emailFromSessionClaims(
      authState.sessionClaims as Record<string, unknown> | undefined
    )
    if (claimEmail) return claimEmail

    try {
      const clerkUser = await currentUser()
      const email = (
        clerkUser?.emailAddresses.find((e) => e.id === clerkUser.primaryEmailAddressId)
          ?.emailAddress ||
        clerkUser?.emailAddresses[0]?.emailAddress ||
        ''
      ).trim()

      if (email) return email.toLowerCase()

      const fallbackEmail = await emailFromClerkUserId(authState.userId)
      if (fallbackEmail) return fallbackEmail
    } catch {
      const fallbackEmail = await emailFromClerkUserId(authState.userId)
      if (fallbackEmail) return fallbackEmail
    }
  }

  if (request) {
    const header = request.headers.get('authorization')
    if (header?.startsWith('Bearer ')) {
      const token = header.slice('Bearer '.length).trim()
      const secretKey = process.env.CLERK_SECRET_KEY
      if (token && secretKey) {
        try {
          const { verifyToken } = await import('@clerk/backend')
          const payload = await verifyToken(token, { secretKey })
          const claimEmail = emailFromSessionClaims(payload as Record<string, unknown>)
          if (claimEmail) return claimEmail
          const userId = typeof payload.sub === 'string' ? payload.sub : null
          if (userId) return emailFromClerkUserId(userId)
        } catch {
          /* ignore */
        }
      }
    }
  }

  return null
}

/** Resolve admin access via backend RBAC (server-side; not email-only). */
export async function resolveAdminAccess(
  request?: NextRequest
): Promise<{ email: string; session: AdminSession } | null> {
  const email = await resolveClerkEmail(request)
  if (!email) return null

  const signedHeaders = adminProxyHeaders(email)
  if (!signedHeaders) return null

  const authState = await auth()
  const headers: Record<string, string> = {
    ...signedHeaders,
  }

  const incomingAuth = request?.headers.get('authorization')
  const clerkToken =
    incomingAuth?.startsWith('Bearer ') ? incomingAuth.slice('Bearer '.length).trim() : null
  const token = clerkToken || (await authState.getToken())
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const res = await fetch(`${getBackendUrl()}/api/admin/security/me`, {
    headers,
    cache: 'no-store',
  })

  if (!res.ok) return null
  const session = (await res.json()) as AdminSession
  if (!session.is_admin) return null

  return { email, session }
}

/** @deprecated Use resolveAdminAccess — kept for imports during transition. */
export async function resolveAdminEmail(request?: NextRequest): Promise<string | null> {
  const access = await resolveAdminAccess(request)
  return access?.email ?? null
}
