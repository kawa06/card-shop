'use client'

import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { liveApi } from '@/lib/api'
import { useLiveEventSource } from '@/hooks/useLiveEventSource'
import type { LiveComment, LiveStream } from '@/lib/types'

function applyCommentEvent(comments: LiveComment[], evt: { type: string; payload: Record<string, unknown> }): LiveComment[] {
  const payload = evt.payload as unknown as LiveComment
  if (evt.type === 'comment.created') {
    if (comments.some((c) => c.id === payload.id)) return comments
    return [...comments, payload]
  }
  if (evt.type === 'comment.deleted') {
    return comments.filter((c) => c.id !== payload.id)
  }
  if (evt.type === 'comment.pinned' || evt.type === 'comment.unpinned') {
    return comments
      .map((c) => (c.id === payload.id ? payload : { ...c, is_pinned: evt.type === 'comment.pinned' ? false : c.is_pinned }))
      .map((c) => (evt.type === 'comment.pinned' && c.id !== payload.id ? { ...c, is_pinned: false } : c))
  }
  return comments
}

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
  }, [streamId])

  const onLiveEvent = useCallback(
    (evt: { type: string; payload: Record<string, unknown> }) => {
      if (evt.type === 'stream.updated') {
        setStream(evt.payload as unknown as LiveStream)
        return
      }
      if (evt.type.startsWith('comment.')) {
        setComments((prev) => applyCommentEvent(prev, evt))
        return
      }
      if (evt.type === 'product.activated' || evt.type === 'product.pinned') {
        liveApi.getStream(streamId).then((res) => setStream(res.data)).catch(() => undefined)
      }
    },
    [streamId],
  )

  useLiveEventSource(streamId ? `/api/live/streams/${streamId}/events` : null, onLiveEvent)

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
