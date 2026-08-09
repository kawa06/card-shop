'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { notificationsApi } from '@/lib/api'
import { useBackendAuth } from '@/hooks/useBackendAuth'
import { Button } from '@/components/ui/button'

type NotificationItem = {
  id: number
  type: string
  category: string
  title: string
  body: string
  action_url?: string | null
  is_read: boolean
  created_at: string
}

export default function MypageNotificationsPage() {
  const router = useRouter()
  const { isLoggedIn, isReady, requireAuth } = useBackendAuth()
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unread, setUnread] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isReady || !isLoggedIn) return
    void (async () => {
      setLoading(true)
      try {
        const token = await requireAuth()
        if (!token) return
        const res = await notificationsApi.list({ limit: 50 })
        setItems(res.data.items || [])
        setUnread(Number(res.data.unread_count || 0))
      } catch {
        setItems([])
      } finally {
        setLoading(false)
      }
    })()
  }, [isReady, isLoggedIn, requireAuth])

  if (!isReady || !isLoggedIn) return null

  const onOpen = async (item: NotificationItem) => {
    try {
      if (!item.is_read) {
        await notificationsApi.markRead(item.id)
        setUnread((u) => Math.max(0, u - 1))
        setItems((prev) => prev.map((n) => (n.id === item.id ? { ...n, is_read: true } : n)))
      }
    } catch {
      /* ignore */
    }
    if (item.action_url) router.push(item.action_url)
  }

  const onMarkAll = async () => {
    await notificationsApi.markAllRead()
    setUnread(0)
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })))
  }

  return (
    <div className="container py-8 max-w-2xl px-4">
      <div className="flex items-center justify-between mb-6 gap-3">
        <div>
          <h1 className="text-2xl font-bold" data-testid="mypage-notifications-heading">
            通知
          </h1>
          <p className="text-sm text-gray-500" data-testid="mypage-notifications-unread">
            未読 {unread} 件
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/mypage/notification-settings" className="text-sm text-blue-600 self-center">
            設定
          </Link>
          <Button
            type="button"
            variant="outline"
            size="sm"
            data-testid="notifications-mark-all-read"
            onClick={() => void onMarkAll()}
            disabled={unread === 0}
          >
            全件既読
          </Button>
        </div>
      </div>

      {loading ? (
        <p className="text-gray-500">読み込み中...</p>
      ) : items.length === 0 ? (
        <p className="text-gray-500" data-testid="mypage-notifications-empty">
          通知はありません
        </p>
      ) : (
        <ul className="space-y-2" data-testid="mypage-notifications-list">
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                data-testid={`notification-item-${item.id}`}
                data-read={item.is_read ? 'true' : 'false'}
                className={`w-full text-left border rounded-lg p-4 transition-colors ${
                  item.is_read ? 'bg-white border-gray-200' : 'bg-yellow-50 border-yellow-200'
                }`}
                onClick={() => void onOpen(item)}
              >
                <div className="flex justify-between gap-2">
                  <span className="font-semibold text-sm">{item.title}</span>
                  {!item.is_read && (
                    <span className="text-[10px] font-bold text-yellow-700" data-testid="notification-unread-dot">
                      未読
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-600 mt-1">{item.body}</p>
                <p className="text-xs text-gray-400 mt-2">{new Date(item.created_at).toLocaleString('ja-JP')}</p>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
