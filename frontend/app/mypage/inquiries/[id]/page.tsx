'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft, Loader2, Send } from 'lucide-react'
import { useBackendAuth } from '@/hooks/useBackendAuth'
import { inquiriesApi } from '@/lib/api'
import { InquiryDetail } from '@/lib/types'
import { inquiryCategoryLabel, inquiryStatusLabel, INQUIRY_STATUS_COLORS } from '@/lib/inquiry-labels'
import { useLangStore } from '@/store/lang'
import { toast } from '@/lib/use-toast'
import { Button } from '@/components/ui/button'
import {
  InquiryAttachmentList,
  INQUIRY_ACCEPTED_IMAGE_TYPES,
  validateInquiryFiles,
} from '@/components/inquiries/InquiryAttachmentList'

function formatDate(value: string): string {
  return new Date(value).toLocaleString('ja-JP')
}

export default function InquiryDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter()
  const inquiryId = parseInt(params.id, 10)
  const { isLoggedIn, isReady, requireAuth } = useBackendAuth()
  const { lang } = useLangStore()
  const [inquiry, setInquiry] = useState<InquiryDetail | null>(null)
  const [reply, setReply] = useState('')
  const [replyFiles, setReplyFiles] = useState<File[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSending, setIsSending] = useState(false)
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const load = useCallback(async () => {
    if (!inquiryId) return
    setIsLoading(true)
    try {
      const res = await inquiriesApi.getById(inquiryId)
      setInquiry(res.data)
    } catch {
      toast({ title: '問い合わせの取得に失敗しました', variant: 'destructive' })
    } finally {
      setIsLoading(false)
    }
  }, [inquiryId])

  useEffect(() => {
    if (!isMounted || !isReady) return
    if (!isLoggedIn) {
      router.push('/sign-in')
      return
    }
    void requireAuth().then((token) => {
      if (token) void load()
    })
  }, [isMounted, isReady, isLoggedIn, router, requireAuth, load])

  const handleSend = async () => {
    if (!reply.trim() || !inquiry) return
    setIsSending(true)
    try {
      const res = await inquiriesApi.postMessage(inquiry.id, reply.trim())
      if (replyFiles.length > 0) {
        await inquiriesApi.uploadAttachments(inquiry.id, replyFiles, res.data.id)
      }
      setReply('')
      setReplyFiles([])
      await load()
      toast({ title: lang === 'ja' ? '返信を送信しました' : 'Reply sent' })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast({
        title: '送信に失敗しました',
        description: typeof detail === 'string' ? detail : undefined,
        variant: 'destructive',
      })
    } finally {
      setIsSending(false)
    }
  }

  const canReply = inquiry && !['closed'].includes(inquiry.status)

  if (!isMounted || !isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-3xl">
        <Link href="/mypage/inquiries" className="inline-flex items-center gap-2 text-gray-500 hover:text-gray-900 text-sm mb-6">
          <ArrowLeft className="h-4 w-4" />
          {lang === 'ja' ? '問い合わせ履歴' : 'Inquiry history'}
        </Link>

        {isLoading ? (
          <div className="h-40 bg-gray-50 rounded-lg animate-pulse" />
        ) : !inquiry ? (
          <p className="text-gray-500">問い合わせが見つかりません</p>
        ) : (
          <>
            <div className="mb-6">
              <p className="text-sm text-gray-500 mb-1">{inquiry.inquiry_number}</p>
              <h1 className="text-xl font-bold text-gray-900 mb-2">{inquiry.subject}</h1>
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="text-gray-500">{inquiryCategoryLabel(inquiry.category)}</span>
                <span
                  className={`px-2 py-0.5 rounded border ${INQUIRY_STATUS_COLORS[inquiry.status] || ''}`}
                >
                  {inquiryStatusLabel(inquiry.status)}
                </span>
                {inquiry.related_order_number && (
                  <span className="text-gray-500">注文: {inquiry.related_order_number}</span>
                )}
                {inquiry.related_product_name && (
                  <span className="text-gray-500">商品: {inquiry.related_product_name}</span>
                )}
              </div>
            </div>

            <div className="space-y-4 mb-8">
              {inquiry.messages.map((msg) => {
                const isCustomer = msg.sender_type === 'customer'
                const isSystem = msg.sender_type === 'system'
                return (
                  <div
                    key={msg.id}
                    className={`rounded-lg border p-4 ${
                      isCustomer
                        ? 'border-yellow-400/30 bg-yellow-50/20 ml-8'
                        : isSystem
                          ? 'border-gray-200 bg-gray-50 text-gray-600'
                          : 'border-blue-200 bg-blue-50/30 mr-8'
                    }`}
                  >
                    <div className="flex justify-between text-xs text-gray-500 mb-2">
                      <span>{msg.sender_name || msg.sender_type}</span>
                      <span>{formatDate(msg.created_at)}</span>
                    </div>
                    <p className="text-sm text-gray-900 whitespace-pre-wrap">{msg.message}</p>
                    <InquiryAttachmentList attachments={inquiry.attachments} messageId={msg.id} />
                  </div>
                )
              })}
            </div>

            {canReply ? (
              <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                <textarea
                  rows={4}
                  className="w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm mb-3"
                  placeholder={lang === 'ja' ? '追加のメッセージを入力…' : 'Type your message…'}
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                />
                <input
                  type="file"
                  accept={INQUIRY_ACCEPTED_IMAGE_TYPES}
                  multiple
                  className="block w-full text-sm text-gray-600 mb-3"
                  onChange={(e) => {
                    const selected = Array.from(e.target.files || [])
                    const err = validateInquiryFiles(selected)
                    if (err) {
                      toast({ title: err, variant: 'destructive' })
                      e.target.value = ''
                      return
                    }
                    setReplyFiles(selected)
                  }}
                />
                {replyFiles.length > 0 && (
                  <p className="text-xs text-gray-500 mb-3">{replyFiles.length} 件の画像を添付</p>
                )}
                <Button onClick={() => void handleSend()} disabled={isSending || !reply.trim()}>
                  {isSending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <>
                      <Send className="h-4 w-4 mr-1" />
                      {lang === 'ja' ? '返信を送信' : 'Send reply'}
                    </>
                  )}
                </Button>
              </div>
            ) : (
              <p className="text-sm text-gray-500">
                {lang === 'ja' ? 'この問い合わせは終了しています。' : 'This inquiry is closed.'}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}
