import { NextRequest, NextResponse } from 'next/server'
import { auth, currentUser } from '@clerk/nextjs/server'
import { createSyncPassword } from '@/lib/auth/sync-password'

function getBackendUrl() {
  return (
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.API_URL ||
    'https://backend-production-054e.up.railway.app'
  ).replace(/\/$/, '')
}

async function backendClerkProvision(
  email: string,
  password: string,
  name: string,
  clientIp: string | null,
  userAgent: string | null
) {
  const secret = (process.env.AUTH_SYNC_SECRET || '').trim()
  if (!secret) return null
  const res = await fetch(`${getBackendUrl()}/api/auth/clerk-provision`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Auth-Sync-Secret': secret,
    },
    body: JSON.stringify({
      email,
      password,
      name,
      client_ip: clientIp,
      user_agent: userAgent,
    }),
  })
  const body = await res.json().catch(() => ({}))
  if (res.status === 202) {
    return { requires2fa: true, ...body }
  }
  if (!res.ok) return null
  return body
}

async function backendLogin(email: string, password: string) {
  const res = await fetch(`${getBackendUrl()}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  const body = await res.json().catch(() => ({}))
  if (res.status === 202) {
    return { requires2fa: true, ...body }
  }
  if (!res.ok) return null
  return body
}

async function backendRegister(email: string, password: string, name: string) {
  const res = await fetch(`${getBackendUrl()}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, name }),
  })
  if (res.status === 400) {
    const body = await res.json().catch(() => ({}))
    if (typeof body.detail === 'string' && body.detail.includes('既に使用')) {
      return null
    }
  }
  if (!res.ok) return null
  return res.json()
}

export async function POST(request: NextRequest) {
  try {
    const { userId } = await auth()
    if (!userId) {
      return NextResponse.json(
        { detail: 'ログインセッションが見つかりません' },
        { status: 401 }
      )
    }

    const clerkUser = await currentUser()
    const email = (
      clerkUser?.emailAddresses.find((e) => e.id === clerkUser.primaryEmailAddressId)?.emailAddress
      || clerkUser?.emailAddresses[0]?.emailAddress
      || ''
    ).trim().toLowerCase()

    if (!email) {
      return NextResponse.json(
        { detail: 'メールアドレスが取得できません' },
        { status: 400 }
      )
    }

    const name =
      clerkUser?.firstName ||
      clerkUser?.username ||
      email.split('@')[0]
    const password = createSyncPassword(userId)
    const clientIp =
      request.headers.get('x-forwarded-for')?.split(',')[0]?.trim() ||
      request.headers.get('x-real-ip') ||
      null
    const userAgent = request.headers.get('user-agent')

    let authData = await backendClerkProvision(email, password, name, clientIp, userAgent)
    if (!authData) {
      authData = await backendLogin(email, password)
    }
    if (!authData) {
      authData = await backendRegister(email, password, name)
    }
    if (!authData) {
      authData = await backendLogin(email, password)
    }

    if (authData?.requires_2fa || authData?.requires2fa) {
      return NextResponse.json(
        {
          requires_2fa: true,
          challenge_id: authData.challenge_id,
          user_id: authData.user_id,
          message: authData.message || '認証コードをメールで送信しました',
        },
        { status: 202 }
      )
    }

    if (!authData?.access_token) {
      return NextResponse.json(
        {
          detail: 'バックエンドとの同期に失敗しました。',
        },
        { status: 502 }
      )
    }

    return NextResponse.json({
      access_token: authData.access_token,
      user: {
        ...authData.user,
        is_verified: true,
        is_admin: Boolean(authData.user?.is_admin),
      },
      auth_provider: 'clerk',
    })
  } catch {
    return NextResponse.json({ detail: 'バックエンドとの同期に失敗しました。' }, { status: 500 })
  }
}
