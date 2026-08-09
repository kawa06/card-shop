'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Bell } from 'lucide-react'
import { notificationsApi } from '@/lib/api'
import { useBackendAuth } from '@/hooks/useBackendAuth'

export function UserNotificationBell() {
  const { isLoggedIn, isReady, requireAuth } = useBackendAuth()
  const [unread, setUnread] = useState(0)

  useEffect(() => {
    if (!isReady || !isLoggedIn) return
    void (async () => {
      const token = await requireAuth()
      if (!token) return
      try {
        const res = await notificationsApi.unreadCount()
        setUnread(Number(res.data.unread_count || 0))
      } catch {
        setUnread(0)
      }
    })()
  }, [isReady, isLoggedIn, requireAuth])

  if (!isReady || !isLoggedIn) return null

  return (
    <Link
      href="/mypage/notifications"
      className="relative inline-flex h-9 w-9 items-center justify-center rounded-md text-gray-600 hover:bg-gray-100 hover:text-gray-900"
      data-testid="header-notification-bell"
      aria-label="通知"
    >
      <Bell className="h-5 w-5" />
      {unread > 0 && (
        <span
          className="absolute -top-1 -right-1 h-5 min-w-5 px-1 rounded-full bg-yellow-400 text-gray-950 text-[10px] font-bold flex items-center justify-center"
          data-testid="header-notification-badge"
        >
          {unread > 99 ? '99+' : unread}
        </span>
      )}
    </Link>
  )
}
