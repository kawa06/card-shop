'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2, Send } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminInquiriesApi } from '@/lib/api'
import { AdminInquiryDetail, InquiryTemplate } from '@/lib/types'
import { inquiryCategoryLabel, inquiryStatusLabel, INQUIRY_STATUS_COLORS } from '@/lib/inquiry-labels'
import { toast } from '@/lib/use-toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  InquiryAttachmentList,
  INQUIRY_ACCEPTED_IMAGE_TYPES,
  validateInquiryFiles,
} from '@/components/inquiries/InquiryAttachmentList'

const STATUS_OPTIONS = [
  'waiting_admin',
  'waiting_customer',
  'in_progress',
  'resolved',
  'closed',
]

function formatDate(value: string): string {
  return new Date(value).toLocaleString('ja-JP')
}

export default function AdminInquiryDetailPage({ params }: { params: { id: string } }) {
  const inquiryId = parseInt(params.id, 10)
  const { isReady } = useAdminGuard()
  const [inquiry, setInquiry] = useState<AdminInquiryDetail | null>(null)
  const [templates, setTemplates] = useState<InquiryTemplate[]>([])
  const [message, setMessage] = useState('')
  const [isInternal, setIsInternal] = useState(false)
  const [templateId, setTemplateId] = useState('')
  const [reason, setReason] = useState('')
  const [newStatus, setNewStatus] = useState('')
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
      const [detailRes, tplRes] = await Promise.all([
        adminInquiriesApi.getById(inquiryId),
        adminInquiriesApi.getReplyTemplates(),
      ])
      setInquiry(detailRes.data)
      setNewStatus(detailRes.data.status)
      setTemplates(tplRes.data || [])
    } catch {
      toast({ title: '問い合わせの取得に失敗しました', variant: 'destructive' })
    } finally {
      setIsLoading(false)
    }
  }, [inquiryId])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void load()
  }, [isMounted, isReady, load])

  const handleTemplatePreview = async (value: string) => {
    setTemplateId(value)
    if (!value || !inquiry) return
    try {
      const res = await adminInquiriesApi.previewTemplate(parseInt(value, 10), inquiry.id, reason || undefined)
      setMessage(res.data.body)
    } catch {
      toast({ title: 'テンプレートの読み込みに失敗しました', variant: 'destructive' })
    }
  }

  const handleReply = async () => {
    if (!inquiry || (!message.trim() && !templateId)) return
    setIsSending(true)
    try {
      const res = await adminInquiriesApi.reply(inquiry.id, {
        message: message.trim(),
        is_internal_note: isInternal,
        template_id: templateId ? parseInt(templateId, 10) : null,
        status: newStatus !== inquiry.status ? newStatus : null,
        reason: reason || null,
      })
      if (!isInternal && replyFiles.length > 0) {
        await adminInquiriesApi.uploadAttachments(inquiry.id, replyFiles, res.data.id)
      }
      setMessage('')
      setTemplateId('')
      setReplyFiles([])
      await load()
      toast({ title: isInternal ? '内部メモを保存しました' : '返信を送信しました' })
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

  const handleStatusOnly = async () => {
    if (!inquiry || newStatus === inquiry.status) return
    try {
      await adminInquiriesApi.update(inquiry.id, { status: newStatus })
      await load()
      toast({ title: 'ステータスを更新しました' })
    } catch {
      toast({ title: '更新に失敗しました', variant: 'destructive' })
    }
  }

  if (!isMounted || !isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-4xl">
        <Link href="/admin/inquiries" className="inline-flex items-center gap-2 text-gray-500 hover:text-gray-900 text-sm mb-6">
          <ArrowLeft className="h-4 w-4" />
          問い合わせ一覧
        </Link>

        {isLoading ? (
          <div className="h-40 bg-gray-50 rounded-lg animate-pulse" />
        ) : !inquiry ? (
          <p className="text-gray-500">問い合わせが見つかりません</p>
        ) : (
          <>
            <div className="mb-6 flex flex-wrap justify-between gap-4">
              <div>
                <p className="text-sm text-gray-500 font-mono">{inquiry.inquiry_number}</p>
                <h1 className="text-xl font-bold text-gray-900">{inquiry.subject}</h1>
                <div className="flex flex-wrap gap-2 mt-2 text-xs">
                  <span className="text-gray-500">{inquiryCategoryLabel(inquiry.category)}</span>
                  <span className={`px-2 py-0.5 rounded border ${INQUIRY_STATUS_COLORS[inquiry.status] || ''}`}>
                    {inquiryStatusLabel(inquiry.status)}
                  </span>
                </div>
              </div>
              <div className="text-sm text-right">
                <p className="text-gray-900">{inquiry.buyer_name}</p>
                <p className="text-gray-500">{inquiry.buyer_email}</p>
                <p className="text-gray-500">{inquiry.reply_email}</p>
                {inquiry.related_order_number && (
                  <Link
                    href={`/admin/orders/${inquiry.related_order_id}`}
                    className="text-yellow-600 hover:underline text-xs"
                  >
                    注文 {inquiry.related_order_number}
                  </Link>
                )}
              </div>
            </div>

            <div className="space-y-4 mb-8">
              {inquiry.messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`rounded-lg border p-4 ${
                    msg.is_internal_note
                      ? 'border-orange-300 bg-orange-50/40'
                      : msg.sender_type === 'customer'
                        ? 'border-gray-200 bg-gray-50'
                        : msg.sender_type === 'system'
                          ? 'border-gray-200 bg-gray-50 text-gray-600'
                          : 'border-blue-200 bg-blue-50/30'
                  }`}
                >
                  <div className="flex justify-between text-xs text-gray-500 mb-2">
                    <span>
                      {msg.is_internal_note ? '内部メモ' : msg.sender_name || msg.sender_type}
                    </span>
                    <span>{formatDate(msg.created_at)}</span>
                  </div>
                  <p className="text-sm whitespace-pre-wrap">{msg.message}</p>
                  {inquiry.attachments?.length > 0 && (
                    <InquiryAttachmentList attachments={inquiry.attachments} messageId={msg.id} />
                  )}
                </div>
              ))}
            </div>

            <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 space-y-4">
              <h2 className="font-medium text-gray-900">返信 / 内部メモ</h2>

              {templates.length > 0 && (
                <div>
                  <Label>定型返信</Label>
                  <select
                    className="mt-1 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm"
                    value={templateId}
                    onChange={(e) => void handleTemplatePreview(e.target.value)}
                  >
                    <option value="">選択しない</option>
                    {templates.map((tpl) => (
                      <option key={tpl.id} value={String(tpl.id)}>
                        {tpl.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <Label htmlFor="reason">理由（テンプレート用・任意）</Label>
                <Input id="reason" value={reason} onChange={(e) => setReason(e.target.value)} className="mt-1" />
              </div>

              <textarea
                rows={6}
                className="w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="返信内容または内部メモ"
              />

              {!isInternal && (
                <input
                  type="file"
                  accept={INQUIRY_ACCEPTED_IMAGE_TYPES}
                  multiple
                  className="block w-full text-sm text-gray-600"
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
              )}

              <div className="flex flex-wrap items-center gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={isInternal} onChange={(e) => setIsInternal(e.target.checked)} />
                  内部メモ（購入者に非表示）
                </label>
                <div className="flex items-center gap-2">
                  <Label className="text-sm">ステータス</Label>
                  <select
                    className="rounded-md border border-gray-200 px-2 py-1 text-sm"
                    value={newStatus}
                    onChange={(e) => setNewStatus(e.target.value)}
                  >
                    {STATUS_OPTIONS.map((s) => (
                      <option key={s} value={s}>
                        {inquiryStatusLabel(s)}
                      </option>
                    ))}
                  </select>
                  <Button variant="outline" size="sm" onClick={() => void handleStatusOnly()}>
                    更新
                  </Button>
                </div>
              </div>

              <Button onClick={() => void handleReply()} disabled={isSending}>
                {isSending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <>
                    <Send className="h-4 w-4 mr-1" />
                    {isInternal ? 'メモを保存' : '返信を送信'}
                  </>
                )}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
