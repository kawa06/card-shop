'use client'

import { useEffect } from 'react'
import { useUser } from '@clerk/nextjs'
import { useRouter } from 'next/navigation'
import { isAdminEmail } from '@/lib/auth/admin'

/** ログイン直後に、管理者だけ /admin へ、それ以外はトップへ */
export default function AfterSignInPage() {
  const { user, isLoaded } = useUser()
  const router = useRouter()

  useEffect(() => {
    if (!isLoaded) return

    const email = user?.primaryEmailAddress?.emailAddress
    if (isAdminEmail(email)) {
      router.replace('/admin')
      return
    }
    router.replace('/')
  }, [isLoaded, user, router])

  return (
    <div className="min-h-[50vh] flex items-center justify-center">
      <p className="text-gray-500 text-sm">ログイン処理中...</p>
    </div>
  )
}
