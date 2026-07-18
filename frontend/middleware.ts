import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'
import { NextResponse } from 'next/server'

const isAdminRoute = createRouteMatcher(['/admin(.*)'])
const isAdminApiRoute = createRouteMatcher(['/api/admin(.*)'])

export default clerkMiddleware(async (auth, req) => {
  if (isAdminRoute(req) || isAdminApiRoute(req)) {
    const { userId } = await auth()

    if (!userId) {
      if (isAdminApiRoute(req)) {
        return NextResponse.json({ detail: 'ログインセッションが見つかりません' }, { status: 401 })
      }
      const signInUrl = new URL('/sign-in', req.url)
      signInUrl.searchParams.set('redirect_url', req.url)
      return NextResponse.redirect(signInUrl)
    }
    // 管理者メールの判定は API プロキシ / クライアント側で行う
  }
})

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
  ],
}
