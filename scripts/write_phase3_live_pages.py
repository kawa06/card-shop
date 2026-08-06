"""Write Phase 3-1 live frontend pages as UTF-8 (Windows-safe)."""
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "frontend" / "app"

ADMIN_LIST = """'use client'

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
"""

ADMIN_DETAIL = """'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { ArrowLeft, Radio, Play, Pause, Square, ExternalLink } from 'lucide-react'
import { useParams } from 'next/navigation'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminLiveApi } from '@/lib/api'
import type { LiveComment, LiveProduct, LiveStream } from '@/lib/types'

export default function AdminLiveDetailPage() {
  const params = useParams<{ id: string }>()
  const streamId = Number(params.id)
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const [stream, setStream] = useState<LiveStream | null>(null)
  const [products, setProducts] = useState<LiveProduct[]>([])
  const [comments, setComments] = useState<LiveComment[]>([])
  const [cardId, setCardId] = useState('')
  const [staffMessage, setStaffMessage] = useState('')

  const reload = async () => {
    const [s, p, c] = await Promise.all([
      adminLiveApi.getStream(streamId),
      adminLiveApi.listProducts(streamId),
      adminLiveApi.listComments(streamId, { limit: 50 }),
    ])
    setStream(s.data)
    setProducts(p.data)
    setComments(c.data.items)
  }

  useEffect(() => {
    if (!isReady || !hasPermission('live.read') || !streamId) return
    reload().catch(() => undefined)
  }, [isReady, hasPermission, streamId])

  if (!isReady || !hasPermission('live.read')) return null
  if (!stream) return <div className="min-h-screen bg-white p-8">読み込み中...</div>

  return (
    <div className="min-h-screen bg-white dark:bg-gray-950">
      <div className="container py-8 max-w-5xl">
        <div className="flex flex-wrap items-center gap-3 mb-6">
          <Link href="/admin/live" className="text-gray-500 hover:text-gray-900 dark:hover:text-gray-100">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <Radio className="h-6 w-6 text-red-500" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{stream.title}</h1>
          <span className="rounded-full bg-gray-100 dark:bg-gray-800 px-3 py-1 text-sm">{stream.status}</span>
          <Link href={`/live/${stream.id}`} className="ml-auto inline-flex items-center gap-1 text-sm text-red-600 hover:underline">
            公開ページ <ExternalLink className="h-4 w-4" />
          </Link>
        </div>

        {hasPermission('live.broadcast') && (
          <div className="flex flex-wrap gap-2 mb-8">
            <button type="button" onClick={() => adminLiveApi.startStream(streamId).then(() => reload())} className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-3 py-2 text-white text-sm"><Play className="h-4 w-4" />開始</button>
            <button type="button" onClick={() => adminLiveApi.pauseStream(streamId).then(() => reload())} className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-3 py-2 text-white text-sm"><Pause className="h-4 w-4" />一時停止</button>
            <button type="button" onClick={() => adminLiveApi.resumeStream(streamId).then(() => reload())} className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-white text-sm">再開</button>
            <button type="button" onClick={() => adminLiveApi.endStream(streamId).then(() => reload())} className="inline-flex items-center gap-2 rounded-lg bg-gray-700 px-3 py-2 text-white text-sm"><Square className="h-4 w-4" />終了</button>
          </div>
        )}

        <div className="grid gap-8 lg:grid-cols-2">
          <section>
            <h2 className="font-semibold mb-3 text-gray-900 dark:text-gray-100">商品</h2>
            {hasPermission('live.write') && (
              <div className="mb-4 flex gap-2">
                <input value={cardId} onChange={(e) => setCardId(e.target.value)} placeholder="カードID" className="flex-1 rounded-lg border px-3 py-2 dark:bg-gray-900 dark:border-gray-700" />
                <button type="button" onClick={() => adminLiveApi.addProduct(streamId, { card_id: Number(cardId) }).then(() => reload())} className="rounded-lg bg-gray-900 text-white px-3 py-2 text-sm dark:bg-gray-100 dark:text-gray-900">追加</button>
              </div>
            )}
            <ul className="space-y-2">
              {products.map((p) => (
                <li key={p.id} className="rounded-lg border p-3 dark:border-gray-800">
                  <p className="font-medium">{p.card_name || `Card #${p.card_id}`}</p>
                  <p className="text-sm text-gray-500">¥{(p.display_price ?? p.card_price ?? 0).toLocaleString('ja-JP')}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {hasPermission('live.write') && (
                      <>
                        <button type="button" onClick={() => adminLiveApi.activateProduct(streamId, p.id).then(() => reload())} className={`text-xs rounded px-2 py-1 ${p.is_active ? 'bg-red-100 text-red-700' : 'bg-gray-100'}`}>表示中</button>
                        <button type="button" onClick={() => adminLiveApi.pinProduct(streamId, p.id).then(() => reload())} className={`text-xs rounded px-2 py-1 ${p.is_pinned ? 'bg-amber-100 text-amber-700' : 'bg-gray-100'}`}>固定</button>
                      </>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="font-semibold mb-3 text-gray-900 dark:text-gray-100">コメント</h2>
            {hasPermission('live.moderate') && (
              <div className="mb-4 flex gap-2">
                <input value={staffMessage} onChange={(e) => setStaffMessage(e.target.value)} placeholder="スタッフコメント" className="flex-1 rounded-lg border px-3 py-2 dark:bg-gray-900 dark:border-gray-700" />
                <button type="button" onClick={() => adminLiveApi.postStaffComment(streamId, { message: staffMessage, sender_type: 'staff' }).then(() => { setStaffMessage(''); reload() })} className="rounded-lg bg-sky-600 text-white px-3 py-2 text-sm">送信</button>
              </div>
            )}
            <ul className="space-y-2 max-h-[480px] overflow-y-auto">
              {comments.map((c) => (
                <li key={c.id} className="rounded-lg border p-3 text-sm dark:border-gray-800">
                  <div className="flex justify-between gap-2">
                    <span className="font-medium">{c.sender_name || c.sender_type}{c.is_pinned ? ' 📌' : ''}</span>
                    {hasPermission('live.moderate') && (
                      <div className="flex gap-2">
                        <button type="button" onClick={() => adminLiveApi.pinComment(streamId, c.id, !c.is_pinned).then(() => reload())} className="text-xs text-amber-600">固定</button>
                        <button type="button" onClick={() => adminLiveApi.deleteComment(streamId, c.id).then(() => reload())} className="text-xs text-red-600">削除</button>
                      </div>
                    )}
                  </div>
                  <p className="mt-1 text-gray-700 dark:text-gray-300">{c.message}</p>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </div>
  )
}
"""

PUBLIC_VIEW = """'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { liveApi } from '@/lib/api'
import type { LiveComment, LiveStream } from '@/lib/types'

export default function LiveViewerPage() {
  const params = useParams<{ id: string }>()
  const streamId = Number(params.id)
  const [stream, setStream] = useState<LiveStream | null>(null)
  const [comments, setComments] = useState<LiveComment[]>([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const reloadComments = () => liveApi.listComments(streamId, { limit: 100 }).then((res) => setComments(res.data.items.reverse()))

  useEffect(() => {
    if (!streamId) return
    liveApi.getStream(streamId).then((res) => setStream(res.data)).catch(() => setError('配信が見つかりません'))
    reloadComments().catch(() => undefined)
    const timer = setInterval(() => { reloadComments().catch(() => undefined) }, 5000)
    return () => clearInterval(timer)
  }, [streamId])

  const submit = async () => {
    if (!message.trim()) return
    setError('')
    try {
      await liveApi.postComment(streamId, message.trim())
      setMessage('')
      await reloadComments()
    } catch {
      setError('コメント送信にはログインが必要です')
    }
  }

  if (error && !stream) {
    return <div className="min-h-screen flex items-center justify-center bg-gray-950 text-gray-200">{error}</div>
  }
  if (!stream) {
    return <div className="min-h-screen flex items-center justify-center bg-gray-950 text-gray-200">読み込み中...</div>
  }

  const product = stream.active_product || stream.pinned_product

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <div className="mx-auto max-w-6xl px-4 py-6 grid gap-6 lg:grid-cols-[2fr_1fr]">
        <section>
          <h1 className="text-2xl font-bold mb-2">{stream.title}</h1>
          <p className="text-sm text-gray-400 mb-4">{stream.status === 'live' ? 'LIVE' : stream.status}</p>
          <div className="aspect-video rounded-xl bg-black/60 border border-gray-800 overflow-hidden mb-4">
            {stream.embed_url ? (
              <iframe src={stream.embed_url} title={stream.title} className="h-full w-full" allowFullScreen />
            ) : (
              <div className="h-full flex items-center justify-center text-gray-500">配信URL未設定</div>
            )}
          </div>
          {product && (
            <div className="rounded-xl border border-gray-800 p-4 flex gap-4 items-center">
              {product.card_image_url && <img src={product.card_image_url} alt="" className="h-20 w-20 object-contain rounded bg-white/5" />}
              <div>
                <p className="font-semibold">{product.card_name}</p>
                <p className="text-yellow-400 text-lg">¥{(product.display_price ?? product.card_price ?? 0).toLocaleString('ja-JP')}</p>
              </div>
            </div>
          )}
        </section>
        <section className="flex flex-col min-h-[420px]">
          <h2 className="font-semibold mb-3">コメント</h2>
          <div className="flex-1 overflow-y-auto space-y-2 mb-4 rounded-xl border border-gray-800 p-3 bg-black/20">
            {comments.map((c) => (
              <div key={c.id} className="text-sm">
                <span className="font-medium text-sky-300">{c.sender_name || c.sender_type}</span>
                {c.is_pinned && <span className="ml-1 text-amber-400">📌</span>}
                <p className="text-gray-200">{c.message}</p>
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <input value={message} onChange={(e) => setMessage(e.target.value)} placeholder="コメントを入力" className="flex-1 rounded-lg bg-gray-900 border border-gray-700 px-3 py-2" />
            <button type="button" onClick={submit} className="rounded-lg bg-red-600 px-4 py-2 font-medium">送信</button>
          </div>
          {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
        </section>
      </div>
    </div>
  )
}
"""

FILES = {
    BASE / "admin" / "live" / "page.tsx": ADMIN_LIST,
    BASE / "admin" / "live" / "[id]" / "page.tsx": ADMIN_DETAIL,
    BASE / "live" / "[id]" / "page.tsx": PUBLIC_VIEW,
}

if __name__ == "__main__":
    for path, content in FILES.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print("wrote", path)
