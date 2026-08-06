import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@clerk/nextjs/server'
import { resolveAdminAccess } from '@/lib/auth/resolve-admin-email'
import { adminProxyHeaders } from '@/lib/auth/admin-proxy-signature'

function getBackendUrl() {
  return (
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.API_URL ||
    'https://backend-production-054e.up.railway.app'
  ).replace(/\/$/, '')
}

async function proxyToBackend(request: NextRequest, pathSegments: string[]) {
  const authState = await auth()
  const access = await resolveAdminAccess(request)

  if (!access) {
    if (!authState.userId) {
      return NextResponse.json(
        { detail: 'ログインセッションが見つかりません' },
        { status: 401 }
      )
    }
    return NextResponse.json({ detail: '管理者権限が必要です' }, { status: 403 })
  }

  const email = access.email

  const signedHeaders = adminProxyHeaders(email)
  if (!signedHeaders) {
    return NextResponse.json(
      { detail: '管理APIを利用できません' },
      { status: 503 }
    )
  }

  const path = pathSegments.join('/')
  const search = request.nextUrl.search
  const targetUrl = `${getBackendUrl()}/api/admin/${path}${search}`

  const headers = new Headers()
  const contentType = request.headers.get('content-type')
  if (contentType) headers.set('Content-Type', contentType)
  Object.entries(signedHeaders).forEach(([key, value]) => headers.set(key, value))

  const incomingAuth = request.headers.get('authorization')
  const clerkToken =
    incomingAuth?.startsWith('Bearer ') ? incomingAuth.slice('Bearer '.length).trim() : null
  const token = clerkToken || (await authState.getToken())
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
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
  const responseHeaders = new Headers()
  const upstreamType = upstream.headers.get('content-type')
  if (upstreamType) responseHeaders.set('Content-Type', upstreamType)
  responseHeaders.set('Cache-Control', 'no-cache')

  if (upstreamType?.includes('text/event-stream') && upstream.body) {
    responseHeaders.set('Connection', 'keep-alive')
    responseHeaders.set('X-Accel-Buffering', 'no')
    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    })
  }

  const body = await upstream.arrayBuffer()
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
