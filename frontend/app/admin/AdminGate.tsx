'use client'

import { useAdminGuard } from '@/hooks/useAdminGuard'
import { Button } from '@/components/ui/button'

export function AdminGate({ children }: { children: React.ReactNode }) {
  const { isReady, isSyncing, syncError, retrySync } = useAdminGuard()

  if (!isReady) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center px-4">
        <div className="text-center space-y-4 max-w-md">
          {syncError ? (
            <>
              <p className="text-red-600 text-sm">{syncError}</p>
              <p className="text-gray-500 text-xs">
                管理者操作にはバックエンド認証の同期が必要です。再試行するか、ページを再読み込みしてください。
              </p>
              <Button onClick={() => retrySync()} disabled={isSyncing} className="bg-sky-600 text-white">
                {isSyncing ? '同期中...' : '再試行'}
              </Button>
            </>
          ) : (
            <p className="text-gray-400 animate-pulse">
              {isSyncing ? '認証を同期中...' : '読み込み中...'}
            </p>
          )}
        </div>
      </div>
    )
  }

  return <>{children}</>
}
