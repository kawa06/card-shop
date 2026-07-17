'use client'

type TokenGetter = () => Promise<string | null>

let tokenGetter: TokenGetter | null = null

export function setClerkTokenGetter(getter: TokenGetter | null) {
  tokenGetter = getter
}

export async function getClerkSessionToken(): Promise<string | null> {
  if (!tokenGetter) return null
  try {
    return await tokenGetter()
  } catch {
    return null
  }
}
