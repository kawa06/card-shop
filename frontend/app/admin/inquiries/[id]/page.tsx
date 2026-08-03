'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Eye, Loader2, Monitor, Moon, RotateCcw, Save, Send, Smartphone } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminInquiriesApi } from '@/lib/api'
import {
  AdminInquiryDetail,
  InquiryEmailLog,
  InquiryEmailTemplateOption,
  InquiryTemplate,
} from '@/lib/types'
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
  const [emailTemplates, setEmailTemplates] = useState<InquiryEmailTemplateOption[]>([])
  const [emailLogs, setEmailLogs] = useState<InquiryEmailLog[]>([])
  const [message, setMessage] = useState('')
  const [isInternal, setIsInternal] = useState(false)
  const [templateId, setTemplateId] = useState('')
  const [emailTemplateKey, setEmailTemplateKey] = useState('inquiry_admin_reply')
  const [sendEmail, setSendEmail] = useState(true)
  const [reason, setReason] = useState('')
  const [newStatus, setNewStatus] = useState('')
  const [replyFiles, setReplyFiles] = useState<File[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSending, setIsSending] = useState(false)
  const [isSavingDraft, setIsSavingDraft] = useState(false)
  const [isMounted, setIsMounted] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [previewMode, setPreviewMode] = useState<'desktop' | 'mobile' | 'dark'>('desktop')
  const [previewHtml, setPreviewHtml] = useState('')
  const [previewSubject, setPreviewSubject] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const load = useCallback(async () => {
    if (!inquiryId) return
    setIsLoading(true)
    try {
      const [detailRes, tplRes, emailTplRes, logsRes, draftRes] = await Promise.all([
        adminInquiriesApi.getById(inquiryId),
        adminInquiriesApi.getReplyTemplates(),
        adminInquiriesApi.getEmailTemplates(),
        adminInquiriesApi.getEmailLogs(inquiryId),
        adminInquiriesApi.getDraft(inquiryId).catch(() => ({ data: null })),
      ])
      setInquiry(detailRes.data)
      setNewStatus(detailRes.data.status)
      setTemplates(tplRes.data || [])
      setEmailTemplates(emailTplRes.data || [])
      setEmailLogs(logsRes.data || [])
      const draft = draftRes.data
      if (draft) {
        setMessage(draft.message || '')
        setEmailTemplateKey(draft.email_template_key || 'inquiry_admin_reply')
        setSendEmail(draft.send_email ?? true)
        if (draft.new_status) setNewStatus(draft.new_status)
        if (draft.reason) setReason(draft.reason)
      }
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

  const refreshPreview = useCallback(async () => {
    if (!inquiry) return
    setPreviewLoading(true)
    try {
      const res = await adminInquiriesApi.previewEmail(inquiry.id, {
        email_template_key: emailTemplateKey,
        reply_text: message,
        include_reply_content: true,
        force_dark: previewMode === 'dark',
      })
      setPreviewHtml(res.data.html)
      setPreviewSubject(res.data.subject)
    } catch {
      setPreviewHtml('')
      toast({ title: 'プレビューの取得に失敗しました', variant: 'destructive' })
    } finally {
      setPreviewLoading(false)
    }
  }, [inquiry, emailTemplateKey, message, previewMode])

  useEffect(() => {
    if (!showPreview || !inquiry) return
    const timer = setTimeout(() => void refreshPreview(), 400)
    return () => clearTimeout(timer)
  }, [showPreview, inquiry, emailTemplateKey, message, previewMode, refreshPreview])

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

  const handleReply = async (saveDraft = false) => {
    if (!inquiry || (!message.trim() && !templateId && !saveDraft)) return
    if (saveDraft) setIsSavingDraft(true)
    else setIsSending(true)
    try {
      const res = await adminInquiriesApi.reply(inquiry.id, {
        message: message.trim(),
        is_internal_note: isInternal,
        template_id: templateId ? parseInt(templateId, 10) : null,
        status: newStatus !== inquiry.status ? newStatus : null,
        reason: reason || null,
        email_template_key: emailTemplateKey,
        send_email: sendEmail,
        save_draft: saveDraft,
      })
      if (saveDraft) {
        toast({ title: '下書きを保存しました' })
        return
      }
      if (!isInternal && replyFiles.length > 0 && res.data.id) {
        await adminInquiriesApi.uploadAttachments(inquiry.id, replyFiles, res.data.id)
      }
      setMessage('')
      setTemplateId('')
      setReplyFiles([])
      await load()
      toast({ title: isInternal ? '内部メモを保存しました' : sendEmail ? '返信を送信しました' : '返信を保存しました（メール未送信）' })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast({
        title: saveDraft ? '下書き保存に失敗しました' : '送信に失敗しました',
        description: typeof detail === 'string' ? detail : undefined,
        variant: 'destructive',
      })
    } finally {
      setIsSending(false)
      setIsSavingDraft(false)
    }
  }

  const handleResend = async (log: InquiryEmailLog) => {
    if (!inquiry) return
    try {
      await adminInquiriesApi.resendEmail(inquiry.id, {
        event_key: log.template_key,
        reply_text: message || undefined,
      })
      await load()
      toast({ title: 'メールを再送しました' })
    } catch {
      toast({ title: '再送に失敗しました', variant: 'destructive' })
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
                {inquiry.related_product_name && (
                  <p className="text-xs text-gray-500">関連商品: {inquiry.related_product_name}</p>
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

            {emailLogs.length > 0 && (
              <div className="mb-8 border border-gray-200 rounded-lg p-4">
                <h2 className="font-medium text-gray-900 mb-3">メール送信履歴</h2>
                <div className="space-y-2">
                  {emailLogs.map((log) => (
                    <div key={log.id} className="flex flex-wrap items-center justify-between gap-2 text-sm border-b border-gray-100 pb-2">
                      <div>
                        <p className="font-medium text-gray-900">{log.template_name || log.template_key}</p>
                        <p className="text-xs text-gray-500">{log.subject}</p>
                        <p className="text-xs text-gray-400">
                          {log.sent_at ? formatDate(log.sent_at) : '—'} · {log.sent_by_name || '自動'} · {log.recipient}
                        </p>
                        {log.error_message && <p className="text-xs text-red-600">{log.error_message}</p>}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-0.5 rounded ${log.status === 'sent' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                          {log.status === 'sent' ? '成功' : '失敗'}
                        </span>
                        {log.status !== 'sent' && (
                          <Button variant="outline" size="sm" onClick={() => void handleResend(log)}>
                            <RotateCcw className="h-3 w-3 mr-1" />
                            再送
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 space-y-4">
              <h2 className="font-medium text-gray-900">返信 / 内部メモ</h2>

              {templates.length > 0 && (
                <div>
                  <Label>定型返信（本文）</Label>
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

              {!isInternal && emailTemplates.length > 0 && (
                <div>
                  <Label>メールテンプレート</Label>
                  <select
                    className="mt-1 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm"
                    value={emailTemplateKey}
                    onChange={(e) => setEmailTemplateKey(e.target.value)}
                  >
                    {emailTemplates.map((tpl) => (
                      <option key={tpl.event_key} value={tpl.event_key}>
                        {tpl.label}
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
                {!isInternal && (
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={sendEmail} onChange={(e) => setSendEmail(e.target.checked)} />
                    メールを送信する
                  </label>
                )}
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

              <div className="flex flex-wrap gap-2">
                {!isInternal && (
                  <Button variant="outline" onClick={() => setShowPreview(true)} disabled={!message.trim()}>
                    <Eye className="h-4 w-4 mr-1" />
                    メールプレビュー
                  </Button>
                )}
                {!isInternal && (
                  <Button variant="outline" onClick={() => void handleReply(true)} disabled={isSavingDraft}>
                    {isSavingDraft ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
                    下書き保存
                  </Button>
                )}
                <Button onClick={() => void handleReply(false)} disabled={isSending}>
                  {isSending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <>
                      <Send className="h-4 w-4 mr-1" />
                      {isInternal ? 'メモを保存' : sendEmail ? '返信を送信' : '返信を保存（メールなし）'}
                    </>
                  )}
                </Button>
              </div>
            </div>
          </>
        )}
      </div>

      {showPreview && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={() => setShowPreview(false)}>
          <div
            className="bg-white rounded-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="font-semibold text-gray-900">メールプレビュー</h3>
                <p className="text-sm text-gray-500 truncate">{previewSubject}</p>
              </div>
              <div className="flex gap-1">
                {(['desktop', 'mobile', 'dark'] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setPreviewMode(mode)}
                    className={`p-2 rounded ${previewMode === mode ? 'bg-yellow-100 text-yellow-800' : 'text-gray-500 hover:bg-gray-100'}`}
                  >
                    {mode === 'desktop' && <Monitor className="h-4 w-4" />}
                    {mode === 'mobile' && <Smartphone className="h-4 w-4" />}
                    {mode === 'dark' && <Moon className="h-4 w-4" />}
                  </button>
                ))}
                <Button variant="outline" size="sm" onClick={() => setShowPreview(false)}>
                  閉じる
                </Button>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-4 bg-gray-100 flex justify-center">
              {previewLoading ? (
                <Loader2 className="h-8 w-8 animate-spin text-gray-400 my-12" />
              ) : (
                <div
                  className={`bg-white shadow-lg overflow-hidden ${
                    previewMode === 'mobile' ? 'w-[375px]' : 'w-full max-w-[640px]'
                  } ${previewMode === 'dark' ? 'dark-preview invert hue-rotate-180' : ''}`}
                  dangerouslySetInnerHTML={{ __html: previewHtml }}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
