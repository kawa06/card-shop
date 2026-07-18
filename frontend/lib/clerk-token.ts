'use client'

type TokenGetter = () => Promise<string | null>

let tokenGetter: TokenGetter | null = null

export function setClerkTokenGetter(getter: TokenGetter | null) {
  tokenGetter = getter
}

export async function getClerkSessionToken(): Promise<string | null> {
  if (tokenGetter) {
    try {
      const token = await tokenGetter()
      if (token) return token
    } catch {
      // fall through to window.Clerk
    }
  }

  if (typeof window === 'undefined') return null

  try {
    const clerk = (
      window as { Clerk?: { session?: { getToken: () => Promise<string | null> } } }
    ).Clerk
    return (await clerk?.session?.getToken()) ?? null
  } catch {
    return null
  }
}
