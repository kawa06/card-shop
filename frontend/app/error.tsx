'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <div className="min-h-[60vh] flex items-center justify-center px-6">
      <div className="max-w-md text-center space-y-4">
        <p className="text-sm font-semibold text-red-600">500</p>
        <h1 className="text-2xl font-bold text-gray-900">エラーが発生しました</h1>
        <p className="text-gray-600 text-sm">
          一時的な問題の可能性があります。しばらくしてから再度お試しください。
        </p>
        <div className="flex flex-col gap-3 pt-2">
          <Button onClick={reset} className="bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold">
            再試行
          </Button>
          <Link href="/">
            <Button variant="outline" className="w-full">
              トップへ戻る
            </Button>
          </Link>
        </div>
      </div>
    </div>
  )
}
