'use client'

import { useAdminGuard } from '@/hooks/useAdminGuard'

export function AdminGate({ children }: { children: React.ReactNode }) {
  const { isReady, isSyncing, syncError, retrySync } = useAdminGuard()

  if (!isReady) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center px-4">
        {syncError ? (
          <div className="text-center space-y-3">
            <p className="text-sm text-gray-600">{syncError}</p>
            <button
              type="button"
              onClick={() => void retrySync()}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
            >
              再試行
            </button>
          </div>
        ) : (
          <p className="text-gray-400 animate-pulse">
            {isSyncing ? '読み込み中...' : '移動中...'}
          </p>
        )}
      </div>
    )
  }

  return <>{children}</>
}
