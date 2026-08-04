'use client'

import { useEffect, useRef, useState } from 'react'
import { Bell } from 'lucide-react'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminNotificationsApi } from '@/lib/api'
import type { AdminInAppNotification } from '@/lib/types'

export function AdminNotificationBell() {
  const { hasPermission } = useAdminPermissions()
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<AdminInAppNotification[]>([])
  const panelRef = useRef<HTMLDivElement>(null)
  const canRead = hasPermission('admin.email.read')

  useEffect(() => {
    if (!canRead) return
    void adminNotificationsApi.getUnreadCount().then((res) => setUnread(res.data.count)).catch(() => {})
  }, [canRead])

  useEffect(() => {
    if (!open || !canRead) return
    void adminNotificationsApi.list({ limit: 15 }).then((res) => setItems(res.data)).catch(() => {})
  }, [open, canRead])

  useEffect(() => {
    if (!open) return
    const onDocClick = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [open])

  if (!canRead) return null

  return (
    <div className="relative" ref={panelRef}>
      <button type="button" aria-label="通知" onClick={() => setOpen((v) => !v)} className="relative rounded-md p-2 text-gray-600 hover:bg-gray-100">
        <Bell className="h-5 w-5" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] rounded-full bg-red-500 px-1 text-[10px] font-bold text-white text-center">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-72 max-h-80 overflow-y-auto rounded-lg border bg-white shadow-lg">
          {items.length === 0 ? (
            <p className="px-4 py-6 text-sm text-gray-500">通知はありません</p>
          ) : (
            items.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`w-full text-left px-4 py-3 border-b text-sm hover:bg-gray-50 ${item.is_read ? '' : 'bg-amber-50'}`}
                onClick={() => {
                  if (!item.is_read) {
                    void adminNotificationsApi.markRead(item.id).then(() => {
                      setUnread((c) => Math.max(0, c - 1))
                      setItems((prev) => prev.map((n) => (n.id === item.id ? { ...n, is_read: true } : n)))
                    })
                  }
                  if (item.reference_type === 'order' && item.reference_id) {
                    window.location.href = `/admin/orders/${item.reference_id}`
                  }
                }}
              >
                <p className="font-medium">{item.title}</p>
                <p className="text-gray-600 mt-1 line-clamp-2">{item.body}</p>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
