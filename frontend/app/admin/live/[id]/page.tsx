'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, Radio, Play, Pause, Square, ExternalLink } from 'lucide-react'
import { useParams } from 'next/navigation'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminLiveApi, adminLiveOfferApi } from '@/lib/api'
import { getClerkSessionToken } from '@/lib/clerk-token'
import { useLiveEventSource } from '@/hooks/useLiveEventSource'
import type { LiveComment, LiveOfferSettings, LiveProduct, LiveStream } from '@/lib/types'

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
  const [commentQuery, setCommentQuery] = useState('')
  const [senderFilter, setSenderFilter] = useState('')
  const [pinnedOnly, setPinnedOnly] = useState(false)
  const [ngWord, setNgWord] = useState('')
  const [ngWords, setNgWords] = useState<{ id: number; word: string; is_active: boolean }[]>([])
  const [offersSettings, setOffersSettings] = useState<LiveOfferSettings | null>(null)

  const reload = async () => {
    const [s, p, c] = await Promise.all([
      adminLiveApi.getStream(streamId),
      adminLiveApi.listProducts(streamId),
      adminLiveApi.listComments(streamId, {
        limit: 50,
        q: commentQuery || undefined,
        sender_type: senderFilter || undefined,
        pinned_only: pinnedOnly || undefined,
      }),
    ])
    setStream(s.data)
    setProducts(p.data)
    setComments(c.data.items)
    if (hasPermission('offer.read') || hasPermission('offer.manage')) {
      adminLiveOfferApi.getSettings(streamId).then((res) => setOffersSettings(res.data)).catch(() => undefined)
    }
    if (hasPermission('live.moderate')) {
      adminLiveApi.listNgWords().then((res) => setNgWords(res.data.filter((w) => w.is_active))).catch(() => undefined)
    }
  }

  useEffect(() => {
    if (!isReady || !hasPermission('live.read') || !streamId) return
    reload().catch(() => undefined)
  }, [isReady, hasPermission, streamId, commentQuery, senderFilter, pinnedOnly])

  const getAuthHeaders = useCallback(async (): Promise<Record<string, string>> => {
    const token = await getClerkSessionToken()
    return token ? { Authorization: `Bearer ${token}` } : {}
  }, [])

  const onLiveEvent = useCallback(
    (evt: { type: string; payload: Record<string, unknown> }) => {
      if (evt.type === 'stream.updated') {
        setStream(evt.payload as unknown as LiveStream)
        return
      }
      if (evt.type.startsWith('comment.')) {
        const payload = evt.payload as unknown as LiveComment
        if (evt.type === 'comment.created') {
          setComments((prev) => (prev.some((c) => c.id === payload.id) ? prev : [payload, ...prev]))
        } else if (evt.type === 'comment.deleted') {
          setComments((prev) => prev.filter((c) => c.id !== payload.id))
        } else {
          setComments((prev) =>
            prev.map((c) => {
              if (c.id === payload.id) return payload
              if (evt.type === 'comment.pinned') return { ...c, is_pinned: false }
              return c
            }),
          )
        }
        return
      }
      if (evt.type === 'product.activated' || evt.type === 'product.pinned') {
        adminLiveApi.listProducts(streamId).then((res) => setProducts(res.data)).catch(() => undefined)
        adminLiveApi.getStream(streamId).then((res) => setStream(res.data)).catch(() => undefined)
      }
      if (evt.type === 'user.muted') {
        reload().catch(() => undefined)
      }
    },
    [streamId],
  )

  useLiveEventSource(
    isReady && hasPermission('live.read') ? `/api/admin/live/streams/${streamId}/events` : null,
    onLiveEvent,
    { getAuthHeaders },
  )

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
          {offersSettings != null && (
            <span className="rounded-full bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-200 px-3 py-1 text-sm">
              希望額 {offersSettings.offers_enabled ? 'ON' : 'OFF'}
            </span>
          )}
          <Link href={`/admin/live/${stream.id}/auctions`} className="inline-flex items-center gap-1 text-sm text-amber-700 hover:underline">
            オークション管理
          </Link>
          <Link href={`/admin/live/${stream.id}/offers`} className="inline-flex items-center gap-1 text-sm text-emerald-700 hover:underline">
            希望額管理
          </Link>
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
            <div className="mb-3 flex flex-col sm:flex-row gap-2">
              <input
                value={commentQuery}
                onChange={(e) => setCommentQuery(e.target.value)}
                placeholder="コメント検索"
                className="flex-1 rounded-lg border px-3 py-2 text-sm dark:bg-gray-900 dark:border-gray-700"
              />
              <select
                value={senderFilter}
                onChange={(e) => setSenderFilter(e.target.value)}
                className="rounded-lg border px-3 py-2 text-sm dark:bg-gray-900 dark:border-gray-700"
              >
                <option value="">すべて</option>
                <option value="customer">購入者</option>
                <option value="staff">スタッフ</option>
                <option value="admin">管理者</option>
              </select>
              <label className="inline-flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
                <input type="checkbox" checked={pinnedOnly} onChange={(e) => setPinnedOnly(e.target.checked)} />
                固定のみ
              </label>
            </div>
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

        {hasPermission('live.moderate') && (
          <section className="mt-8 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
            <h2 className="font-semibold mb-3 text-gray-900 dark:text-gray-100">NGワード</h2>
            <div className="mb-3 flex gap-2">
              <input
                value={ngWord}
                onChange={(e) => setNgWord(e.target.value)}
                placeholder="追加するNGワード"
                className="flex-1 rounded-lg border px-3 py-2 text-sm dark:bg-gray-900 dark:border-gray-700"
              />
              <button
                type="button"
                onClick={() => adminLiveApi.createNgWord(ngWord.trim()).then(() => { setNgWord(''); reload() })}
                className="rounded-lg bg-gray-800 text-white px-3 py-2 text-sm dark:bg-gray-200 dark:text-gray-900"
              >
                追加
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {ngWords.map((w) => (
                <span key={w.id} className="inline-flex items-center gap-2 rounded-full bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 px-3 py-1 text-sm">
                  {w.word}
                  <button type="button" onClick={() => adminLiveApi.deleteNgWord(w.id).then(() => reload())} className="text-xs underline">削除</button>
                </span>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
