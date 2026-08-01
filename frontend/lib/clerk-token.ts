'use client'

type TokenOptions = { skipCache?: boolean }
type TokenGetter = (options?: TokenOptions) => Promise<string | null>

let tokenGetter: TokenGetter | null = null

export function setClerkTokenGetter(getter: TokenGetter | null) {
  tokenGetter = getter
}

export async function getClerkSessionToken(forceRefresh = false): Promise<string | null> {
  const options = forceRefresh ? { skipCache: true } : undefined

  if (tokenGetter) {
    try {
      const token = await tokenGetter(options)
      if (token) return token
    } catch {
      // fall through to window.Clerk
    }
  }

  if (typeof window === 'undefined') return null

  try {
    const clerk = (
      window as {
        Clerk?: {
          session?: {
            getToken: (options?: TokenOptions) => Promise<string | null>
          }
        }
      }
    ).Clerk
    return (await clerk?.session?.getToken(options)) ?? null
  } catch {
    return null
  }
}
