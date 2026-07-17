import { NextResponse } from 'next/server'
import { auth, currentUser } from '@clerk/nextjs/server'
import { createSyncPassword } from '@/lib/auth/sync-password'

function getBackendUrl() {
  return (
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.API_URL ||
    'https://web-production-97eff.up.railway.app'
  ).replace(/\/$/, '')
}

async function backendClerkProvision(email: string, password: string, name: string) {
  const secret = process.env.AUTH_SYNC_SECRET || process.env.CLERK_SECRET_KEY
  if (!secret) return null
  const res = await fetch(`${getBackendUrl()}/api/auth/clerk-provision`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Auth-Sync-Secret': secret,
    },
    body: JSON.stringify({ email, password, name }),
  })
  if (!res.ok) return null
  return res.json()
}

async function backendLogin(email: string, password: string) {
  const res = await fetch(`${getBackendUrl()}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) return null
  return res.json()
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

export async function POST() {
  try {
    const { userId } = auth()
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

    let authData = await backendLogin(email, password)
    if (!authData) {
      authData = await backendClerkProvision(email, password, name)
    }
    if (!authData) {
      authData = await backendRegister(email, password, name)
    }
    if (!authData) {
      authData = await backendLogin(email, password)
    }

    if (!authData?.access_token) {
      return NextResponse.json(
        { detail: 'バックエンドとの同期に失敗しました' },
        { status: 502 }
      )
    }

    return NextResponse.json({
      access_token: authData.access_token,
      user: {
        ...authData.user,
        is_verified: true,
        is_admin: authData.user?.is_admin || email === 'rikukai0609@icloud.com',
      },
      auth_provider: 'clerk',
    })
  } catch (err) {
    const message = err instanceof Error ? err.message : '同期エラー'
    return NextResponse.json({ detail: message }, { status: 500 })
  }
}
