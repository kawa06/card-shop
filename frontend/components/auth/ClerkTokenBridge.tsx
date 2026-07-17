'use client'

import { useEffect } from 'react'
import { useAuth } from '@clerk/nextjs'
import { setClerkTokenGetter } from '@/lib/clerk-token'

export function ClerkTokenBridge() {
  const { getToken, isLoaded } = useAuth()

  useEffect(() => {
    if (!isLoaded) return
    setClerkTokenGetter(() => getToken())
    return () => setClerkTokenGetter(null)
  }, [getToken, isLoaded])

  return null
}
