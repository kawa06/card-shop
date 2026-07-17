import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'
import { NextResponse } from 'next/server'
import { isAdminEmail } from '@/lib/auth/admin'

const isAdminRoute = createRouteMatcher(['/admin(.*)'])

export default clerkMiddleware((auth, req) => {
  if (isAdminRoute(req)) {
    const { userId, sessionClaims } = auth()

    if (!userId) {
      const signInUrl = new URL('/sign-in', req.url)
      signInUrl.searchParams.set('redirect_url', req.url)
      return NextResponse.redirect(signInUrl)
    }

    const email =
      (sessionClaims?.email as string | undefined) ||
      (sessionClaims?.primary_email_address as string | undefined)

    if (!isAdminEmail(email)) {
      return NextResponse.redirect(new URL('/', req.url))
    }
  }
})

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
  ],
}
