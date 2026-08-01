'use client'

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html lang="ja">
      <body className="min-h-screen bg-white text-gray-900 flex items-center justify-center p-6">
        <div className="max-w-md text-center space-y-4">
          <p className="text-sm font-semibold text-red-600">500</p>
          <h1 className="text-2xl font-bold">エラーが発生しました</h1>
          <p className="text-gray-600 text-sm">ページを再読み込みしてください。</p>
          <button
            type="button"
            onClick={reset}
            className="inline-flex items-center justify-center rounded-md bg-yellow-400 px-4 py-2 font-bold text-gray-950 hover:bg-yellow-300"
          >
            再試行
          </button>
        </div>
      </body>
    </html>
  )
}
