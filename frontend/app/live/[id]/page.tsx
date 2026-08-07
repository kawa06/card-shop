'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'next/navigation'
import { liveApi, liveAuctionApi, liveOfferApi } from '@/lib/api'
import { useLiveEventSource } from '@/hooks/useLiveEventSource'
import type { LiveAuction, LiveBid, LiveComment, LiveOffer, LiveOfferPublic, LiveStream } from '@/lib/types'

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

function formatRemaining(endsAt?: string | null, nowMs = Date.now()): string {
  if (!endsAt) return '—'
  const ms = new Date(endsAt).getTime() - nowMs
  if (ms <= 0) return '0:00'
  const total = Math.floor(ms / 1000)
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}



function formatDisplayExpiry(expiresAt?: string | null, nowMs = Date.now()): string {
  if (!expiresAt) return ''
  const ms = new Date(expiresAt).getTime() - nowMs
  if (ms <= 0) return '表示終了'
  const total = Math.floor(ms / 1000)
  const m = Math.floor(total / 60)
  const s = total % 60
  return `残り ${m}:${s.toString().padStart(2, '0')}`
}

function offerStatusMessage(status: LiveOffer['status']): string {
  if (status === 'accepted') return '承認されました。ご購入いただけます。'
  if (status === 'rejected') return '却下されました。'
  if (status === 'held') return '保留中です。しばらくお待ちください。'
  if (status === 'pending') return '審査中です。'
  return status
}

function minNextBid(auction: LiveAuction): number {
  const current = auction.current_price ?? auction.start_price
  return current + auction.min_bid_increment
}

export default function LiveViewerPage() {
  const params = useParams<{ id: string }>()
  const streamId = Number(params.id)
  const [stream, setStream] = useState<LiveStream | null>(null)
  const [comments, setComments] = useState<LiveComment[]>([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const [auctions, setAuctions] = useState<LiveAuction[]>([])
  const [bids, setBids] = useState<LiveBid[]>([])
  const [bidAmount, setBidAmount] = useState('')
  const [bidError, setBidError] = useState('')
  const [nowMs, setNowMs] = useState(() => Date.now())

  const [publicOffers, setPublicOffers] = useState<LiveOfferPublic[]>([])
  const [myOffers, setMyOffers] = useState<LiveOffer[]>([])
  const [offerAmount, setOfferAmount] = useState('1500')
  const [offerError, setOfferError] = useState('')
  const [offerPurchaseMessage, setOfferPurchaseMessage] = useState('')
  const [offersEnabled, setOffersEnabled] = useState(true)

  const activeAuction = useMemo(() => {
    const running = auctions.find((a) => a.status === 'running' || a.status === 'paused')
    return running ?? auctions[0] ?? null
  }, [auctions])

  const reloadComments = () => liveApi.listComments(streamId, { limit: 100 }).then((res) => setComments(res.data.items.reverse()))

  const reloadAuctions = useCallback(() => {
    return liveAuctionApi.list(streamId, { limit: 20 }).then((res) => setAuctions(res.data.items))
  }, [streamId])


  const reloadPublicOffers = useCallback(() => {
    return liveOfferApi.listPublic(streamId, { limit: 30 }).then((res) => setPublicOffers(res.data.items))
  }, [streamId])

  const reloadMyOffers = useCallback(() => {
    return liveOfferApi.listMine(streamId, { limit: 20 }).then((res) => setMyOffers(res.data.items))
  }, [streamId])

  const latestMyOffer = useMemo(() => myOffers[0] ?? null, [myOffers])

  const offersFormVisible = useMemo(() => {
    const product = stream?.active_product || stream?.pinned_product
    if (!product || !offersEnabled) return false
    if (stream?.status !== 'live' && stream?.status !== 'paused') return false
    if (product.offers_enabled === false) return false
    if (stream?.offers_enabled === false) return false
    return true
  }, [stream, offersEnabled])

  const reloadBids = useCallback(
    (auctionId: number) => {
      return liveAuctionApi.listBids(auctionId, { limit: 20 }).then((res) => setBids(res.data.items))
    },
    [],
  )

  useEffect(() => {
    if (!streamId) return
    liveApi.getStream(streamId).then((res) => setStream(res.data)).catch(() => setError('配信が見つかりません'))
    reloadComments().catch(() => undefined)
    reloadAuctions().catch(() => undefined)

    reloadPublicOffers().catch(() => undefined)
    reloadMyOffers().catch(() => undefined)
  }, [streamId, reloadAuctions])

  useEffect(() => {
    if (!activeAuction) {
      setBids([])
      return
    }
    reloadBids(activeAuction.id).catch(() => undefined)
    setBidAmount(String(minNextBid(activeAuction)))
  }, [activeAuction, reloadBids])

  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])


  const upsertPublicOffer = useCallback((offer: LiveOfferPublic) => {
    setPublicOffers((prev) => {
      const idx = prev.findIndex((o) => o.id === offer.id)
      if (idx === -1) return [offer, ...prev]
      return prev.map((o) => (o.id === offer.id ? offer : o))
    })
  }, [])

  const upsertMyOffer = useCallback((offer: LiveOffer) => {
    setMyOffers((prev) => {
      const idx = prev.findIndex((o) => o.id === offer.id)
      if (idx === -1) return [offer, ...prev]
      return prev.map((o) => (o.id === offer.id ? offer : o))
    })
  }, [])

  const upsertAuction = useCallback((auction: LiveAuction) => {
    setAuctions((prev) => {
      const idx = prev.findIndex((a) => a.id === auction.id)
      if (idx === -1) return [auction, ...prev]
      return prev.map((a) => (a.id === auction.id ? auction : a))
    })
  }, [])

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
      if (evt.type.startsWith('auction.')) {
        upsertAuction(evt.payload as unknown as LiveAuction)
        return
      }

      if (evt.type.startsWith('offer.')) {
        const payload = evt.payload as unknown as LiveOffer
        const pub: LiveOfferPublic = {
          id: payload.id,
          amount: payload.amount,
          status: payload.status,
          sender_name: payload.sender_name,
          live_product_id: payload.live_product_id,
          product: payload.product,
          created_at: payload.created_at,
        }
        upsertPublicOffer(pub)
        upsertMyOffer(payload)
        reloadMyOffers().catch(() => undefined)
        return
      }

      if (evt.type.startsWith('bid.')) {
        const auctionId = Number(evt.payload.auction_id)
        if (activeAuction?.id === auctionId) {
          reloadBids(auctionId).catch(() => undefined)
        }
        liveAuctionApi.get(auctionId).then((res) => upsertAuction(res.data)).catch(() => undefined)
        return
      }
      if (evt.type === 'product.activated' || evt.type === 'product.pinned') {
        liveApi.getStream(streamId).then((res) => setStream(res.data)).catch(() => undefined)
      }
    },
    [streamId, activeAuction?.id, upsertAuction, reloadBids, upsertPublicOffer, upsertMyOffer, reloadMyOffers],
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


  const submitOffer = async () => {
    const product = stream?.active_product || stream?.pinned_product
    if (!product) return
    setOfferError('')
    const amount = Number(offerAmount)
    if (!Number.isFinite(amount) || amount <= 0) {
      setOfferError('金額を入力してください')
      return
    }
    try {
      const res = await liveOfferApi.create(streamId, {
        live_product_id: product.id,
        amount,
      })
      upsertMyOffer(res.data)
      await reloadPublicOffers()
      setOfferAmount(String(amount))
    } catch {
      setOfferError('希望額の送信に失敗しました')
    }
  }

  const purchaseAcceptedOffer = async () => {
    if (!latestMyOffer || latestMyOffer.status !== 'accepted') return
    setOfferPurchaseMessage('')
    try {
      const res = await liveOfferApi.purchase(latestMyOffer.id, { shipping_address: 'E2E Offer Purchase' })
      setOfferPurchaseMessage(`注文 #${res.data.order_id} を作成しました`)
    } catch {
      setOfferPurchaseMessage('購入に失敗しました')
    }
  }

  const submitBid = async () => {
    if (!activeAuction) return
    setBidError('')
    const amount = Number(bidAmount)
    if (!Number.isFinite(amount) || amount <= 0) {
      setBidError('入札額を入力してください')
      return
    }
    try {
      const res = await liveAuctionApi.placeBid(activeAuction.id, amount)
      upsertAuction(res.data.auction)
      await reloadBids(activeAuction.id)
      setBidAmount(String(minNextBid(res.data.auction)))
    } catch {
      setBidError('入札に失敗しました')
    }
  }

  if (error && !stream) {
    return <div className="min-h-screen flex items-center justify-center bg-gray-950 text-gray-200">{error}</div>
  }
  if (!stream) {
    return <div className="min-h-screen flex items-center justify-center bg-gray-950 text-gray-200">読み込み中...</div>
  }

  const product = stream.active_product || stream.pinned_product
  const currentPrice = activeAuction ? (activeAuction.current_price ?? activeAuction.start_price) : null
  const minBid = activeAuction ? minNextBid(activeAuction) : null

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
            <div className="rounded-xl border border-gray-800 p-4 flex gap-4 items-center mb-4">
              {product.card_image_url && <img src={product.card_image_url} alt="" className="h-20 w-20 object-contain rounded bg-white/5" />}
              <div>
                <p className="font-semibold">{product.card_name}</p>
                <p className="text-yellow-400 text-lg">¥{(product.display_price ?? product.card_price ?? 0).toLocaleString('ja-JP')}</p>
              </div>
            </div>
          )}


          <div data-testid="live-offers-panel" className="rounded-xl border border-emerald-700/40 bg-emerald-950/20 p-4 mb-4 min-h-[280px] flex flex-col">
            <h2 className="font-semibold mb-3 text-emerald-200 text-lg">希望額</h2>
            <ul className="space-y-2 flex-1 overflow-y-auto max-h-52 mb-4 text-sm">
              {publicOffers.map((o) => (
                <li key={o.id} className="flex justify-between gap-2 border-b border-gray-800/60 py-1">
                  <span className="text-gray-300 truncate">{o.sender_name || 'ユーザー'} · {o.status}</span>
                  <span className="font-medium">¥{o.amount.toLocaleString('ja-JP')}</span>
                </li>
              ))}
              {publicOffers.length === 0 && <li className="text-gray-500">希望額はありません</li>}
            </ul>
            <p className="text-xs text-gray-500 mb-3">表示期限はカードに表示され消えます</p>

            {offersFormVisible && (
              <div className="flex gap-2 mb-4">
                <input
                  data-testid="offer-amount-input"
                  value={offerAmount}
                  onChange={(e) => setOfferAmount(e.target.value)}
                  className="flex-1 rounded-lg bg-gray-900 border border-gray-700 px-3 py-2"
                />
                <button data-testid="offer-submit" type="button" onClick={submitOffer} className="rounded-lg bg-emerald-600 px-4 py-2 font-medium">
                  提出
                </button>
              </div>
            )}
            {offerError && <p className="text-red-400 text-sm mb-2">{offerError}</p>}

            {latestMyOffer && (
              <div data-testid="offer-my-status" className="rounded-lg border border-gray-700 bg-black/30 p-3 text-sm">
                <p className="font-medium text-emerald-200">あなたの希望額: ¥{latestMyOffer.amount.toLocaleString('ja-JP')}</p>
                <p className="text-gray-300 mt-1">{offerStatusMessage(latestMyOffer.status)}</p>
                {latestMyOffer.display_expires_at && latestMyOffer.status === 'pending' && (
                  <p className="text-xs text-gray-500 mt-1">{formatDisplayExpiry(latestMyOffer.display_expires_at, nowMs)}</p>
                )}
                {latestMyOffer.status === 'accepted' && (
                  <button
                    data-testid="offer-purchase"
                    type="button"
                    onClick={purchaseAcceptedOffer}
                    className="mt-3 rounded-lg bg-yellow-500 text-gray-900 px-4 py-2 font-medium"
                  >
                    承認額で購入
                  </button>
                )}
                {offerPurchaseMessage && <p className="text-emerald-300 mt-2">{offerPurchaseMessage}</p>}
              </div>
            )}
          </div>

          {activeAuction && (
            <div data-testid="live-auction-panel" className="rounded-xl border border-amber-700/40 bg-amber-950/20 p-4">
              <h2 className="font-semibold mb-3 text-amber-200">オークション</h2>
              <dl className="grid grid-cols-2 gap-3 text-sm mb-4">
                <div>
                  <dt className="text-gray-400">現在価格</dt>
                  <dd className="text-2xl font-bold text-yellow-400">¥{(currentPrice ?? 0).toLocaleString('ja-JP')}</dd>
                </div>
                <div>
                  <dt className="text-gray-400">残り時間</dt>
                  <dd className="text-xl font-semibold">{formatRemaining(activeAuction.ends_at, nowMs)}</dd>
                </div>
                <div>
                  <dt className="text-gray-400">最小入札額</dt>
                  <dd>¥{(minBid ?? 0).toLocaleString('ja-JP')}</dd>
                </div>
                <div>
                  <dt className="text-gray-400">即決価格</dt>
                  <dd>{activeAuction.buy_now_price != null ? `¥${activeAuction.buy_now_price.toLocaleString('ja-JP')}` : '—'}</dd>
                </div>
              </dl>

              {(activeAuction.status === 'running' || activeAuction.status === 'paused') && (
                <div className="flex gap-2 mb-4">
                  <input
                    data-testid="bid-amount-input"
                    value={bidAmount}
                    onChange={(e) => setBidAmount(e.target.value)}
                    className="flex-1 rounded-lg bg-gray-900 border border-gray-700 px-3 py-2"
                  />
                  <button data-testid="bid-submit" type="button" onClick={submitBid} className="rounded-lg bg-amber-600 px-4 py-2 font-medium">
                    入札
                  </button>
                </div>
              )}
              {bidError && <p className="text-red-400 text-sm mb-3">{bidError}</p>}

              <h3 className="font-medium mb-2 text-gray-200">入札履歴</h3>
              <ul className="space-y-1 max-h-40 overflow-y-auto text-sm">
                {bids.map((b) => (
                  <li key={b.id} className="flex justify-between border-b border-gray-800/60 py-1">
                    <span className="text-gray-400">#{b.user_id}</span>
                    <span>¥{b.amount.toLocaleString('ja-JP')}</span>
                  </li>
                ))}
                {bids.length === 0 && <li className="text-gray-500">入札はありません</li>}
              </ul>
            </div>
          )}
        </section>
        <section className="flex flex-col min-h-[320px] lg:min-h-[420px]">
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
