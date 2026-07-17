'use client'

import { useAdminGuard } from '@/hooks/useAdminGuard'

export function AdminGate({ children }: { children: React.ReactNode }) {
  const { isReady, isSyncing } = useAdminGuard()

  if (!isReady) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center px-4">
        <p className="text-gray-400 animate-pulse">
          {isSyncing ? '読み込み中...' : '読み込み中...'}
        </p>
      </div>
    )
  }

  return <>{children}</>
}
