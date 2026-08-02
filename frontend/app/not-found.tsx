import Link from 'next/link'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'ページが見つかりません',
  robots: {
    index: false,
    follow: false,
  },
}

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4 px-4 text-center">
      <h1 className="text-2xl font-bold text-gray-900">404 — ページが見つかりません</h1>
      <p className="text-gray-500 text-sm max-w-md">
        お探しのページは削除されたか、URLが変更された可能性があります。
      </p>
      <Link
        href="/"
        className="inline-flex items-center rounded-lg bg-yellow-400 px-4 py-2 text-sm font-semibold text-gray-950 hover:bg-yellow-300"
      >
        トップへ戻る
      </Link>
    </div>
  )
}
