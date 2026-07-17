import { NextRequest, NextResponse } from 'next/server'
import { auth, currentUser } from '@clerk/nextjs/server'
import { isAdminEmail } from '@/lib/auth/admin'

function getBackendUrl() {
  return (
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.API_URL ||
    'https://web-production-97eff.up.railway.app'
  ).replace(/\/$/, '')
}

/** Shared with Railway backend/internal_admin_auth.py (override via ADMIN_PROXY_SECRET). */
const ADMIN_PROXY_SECRET = process.env.ADMIN_PROXY_SECRET || 'card-shop-internal-admin-v1'

function getInternalSecret() {
  return ADMIN_PROXY_SECRET
}

async function resolveAdminEmail(): Promise<string | null> {
  const { userId } = auth()
  if (!userId) return null

  const clerkUser = await currentUser()
  const email = (
    clerkUser?.emailAddresses.find((e) => e.id === clerkUser.primaryEmailAddressId)
      ?.emailAddress ||
    clerkUser?.emailAddresses[0]?.emailAddress ||
    ''
  ).trim()

  return isAdminEmail(email) ? email.toLowerCase() : null
}

async function proxyToBackend(request: NextRequest, pathSegments: string[]) {
  const email = await resolveAdminEmail()
  if (!email) {
    return NextResponse.json({ detail: '管理者権限が必要です' }, { status: 403 })
  }

  const secret = getInternalSecret()
  if (!secret) {
    return NextResponse.json(
      { detail: 'サーバー設定（ADMIN_PROXY_SECRET）が不足しています' },
      { status: 500 }
    )
  }

  const path = pathSegments.join('/')
  const search = request.nextUrl.search
  const targetUrl = `${getBackendUrl()}/api/admin/${path}${search}`

  const headers = new Headers()
  const contentType = request.headers.get('content-type')
  if (contentType) headers.set('Content-Type', contentType)
  headers.set('X-Internal-Admin-Secret', secret)
  headers.set('X-Admin-Email', email)

  const { getToken } = await auth()
  const clerkToken = await getToken()
  if (clerkToken) {
    headers.set('Authorization', `Bearer ${clerkToken}`)
  }

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: 'no-store',
  }

  if (request.method !== 'GET' && request.method !== 'HEAD') {
    init.body = await request.arrayBuffer()
  }

  const upstream = await fetch(targetUrl, init)
  const body = await upstream.arrayBuffer()
  const responseHeaders = new Headers()
  const upstreamType = upstream.headers.get('content-type')
  if (upstreamType) responseHeaders.set('Content-Type', upstreamType)

  return new NextResponse(body, {
    status: upstream.status,
    headers: responseHeaders,
  })
}

type RouteContext = { params: { path: string[] } }

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, context.params.path)
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, context.params.path)
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, context.params.path)
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, context.params.path)
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, context.params.path)
}
