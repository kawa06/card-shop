'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { ArrowLeft, Radio, Plus, ChevronRight } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminLiveApi } from '@/lib/api'
import type { LiveStream } from '@/lib/types'

const STATUS_LABEL: Record<string, string> = {
  draft: '下書き',
  scheduled: '予定',
  live: '配信中',
  paused: '一時停止',
  ended: '終了',
}

export default function AdminLivePage() {
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const [streams, setStreams] = useState<LiveStream[]>([])
  const [title, setTitle] = useState('')
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    if (!isReady || !hasPermission('live.read')) return
    adminLiveApi.listStreams().then((res) => setStreams(res.data.items)).finally(() => setLoading(false))
  }, [isReady, hasPermission])

  if (!isReady) return null
  if (!hasPermission('live.read')) {
    return <div className="min-h-screen bg-white p-8 text-gray-700">ライブ配信の閲覧権限がありません。</div>
  }

  const createStream = async () => {
    if (!title.trim() || !hasPermission('live.write')) return
    setCreating(true)
    try {
      const res = await adminLiveApi.createStream({ title: title.trim(), visibility: 'public' })
      setStreams((prev) => [res.data, ...prev])
      setTitle('')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="min-h-screen bg-white dark:bg-gray-950">
      <div className="container py-8 max-w-4xl">
        <div className="flex items-center gap-3 mb-8">
          <Link href="/admin" className="text-gray-500 hover:text-gray-900 dark:hover:text-gray-100">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <Radio className="h-6 w-6 text-red-500" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">ライブ配信管理</h1>
        </div>

        {hasPermission('live.write') && (
          <div className="mb-8 flex flex-col sm:flex-row gap-3">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="新しい配信タイトル"
              className="flex-1 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-4 py-2 text-gray-900 dark:text-gray-100"
            />
            <button
              type="button"
              onClick={createStream}
              disabled={creating || !title.trim()}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-white disabled:opacity-50"
            >
              <Plus className="h-4 w-4" /> 作成
            </button>
          </div>
        )}

        {loading ? (
          <p className="text-gray-500">読み込み中...</p>
        ) : streams.length === 0 ? (
          <p className="text-gray-500">配信がありません。</p>
        ) : (
          <ul className="space-y-3">
            {streams.map((stream) => (
              <li key={stream.id}>
                <Link
                  href={`/admin/live/${stream.id}`}
                  className="flex items-center justify-between rounded-xl border border-gray-200 dark:border-gray-800 p-4 hover:border-red-300 dark:hover:border-red-700"
                >
                  <div>
                    <p className="font-semibold text-gray-900 dark:text-gray-100">{stream.title}</p>
                    <p className="text-sm text-gray-500 mt-1">
                      {STATUS_LABEL[stream.status] || stream.status} · 商品 {stream.product_count} · コメント {stream.comment_count}
                    </p>
                  </div>
                  <ChevronRight className="h-5 w-5 text-gray-400" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
