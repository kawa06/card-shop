'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { useBackendAuth } from '@/hooks/useBackendAuth'
import { useAuthStore } from '@/store/auth'
import { inquiriesApi, ordersApi } from '@/lib/api'
import { InquiryCreatePayload, InquiryTemplate, Order } from '@/lib/types'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { toast } from '@/lib/use-toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  INQUIRY_ACCEPTED_IMAGE_TYPES,
  validateInquiryFiles,
} from '@/components/inquiries/InquiryAttachmentList'

export default function NewInquiryPage() {
  const router = useRouter()
  const { isLoggedIn, isReady, user, requireAuth } = useBackendAuth()
  const { fetchMe } = useAuthStore()
  const { lang } = useLangStore()

  const [categories, setCategories] = useState<{ value: string; label: string }[]>([])
  const [templates, setTemplates] = useState<InquiryTemplate[]>([])
  const [orders, setOrders] = useState<Order[]>([])
  const [category, setCategory] = useState('')
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [replyEmail, setReplyEmail] = useState('')
  const [relatedOrderId, setRelatedOrderId] = useState<string>('')
  const [templateId, setTemplateId] = useState<string>('')
  const [showConfirm, setShowConfirm] = useState(false)
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const loadMeta = useCallback(async () => {
    const [catRes, tplRes, ordRes] = await Promise.all([
      inquiriesApi.getCategories(),
      inquiriesApi.getTemplates(),
      ordersApi.getAll(),
    ])
    setCategories(catRes.data || [])
    setTemplates(tplRes.data || [])
    setOrders(ordRes.data || [])
    if (catRes.data?.[0]) setCategory(catRes.data[0].value)
  }, [])

  useEffect(() => {
    if (!isMounted || !isReady) return
    if (!isLoggedIn) {
      router.push('/sign-in')
      return
    }
    void requireAuth().then((token) => {
      if (token) {
        void fetchMe()
        void loadMeta()
      }
    })
  }, [isMounted, isReady, isLoggedIn, router, requireAuth, fetchMe, loadMeta])

  useEffect(() => {
    if (user?.email) setReplyEmail(user.email)
  }, [user?.email])

  const buildPayload = (): InquiryCreatePayload => ({
    category,
    subject: subject.trim(),
    message: message.trim(),
    reply_email: replyEmail.trim() || undefined,
    related_order_id: relatedOrderId ? parseInt(relatedOrderId, 10) : null,
    template_id: templateId ? parseInt(templateId, 10) : null,
  })

  const handleTemplateChange = async (value: string) => {
    setTemplateId(value)
    if (!value) return
    setIsPreviewLoading(true)
    try {
      const res = await inquiriesApi.previewTemplate(parseInt(value, 10), buildPayload())
      setMessage(res.data.body)
      if (res.data.warnings?.length) {
        toast({
          title: lang === 'ja' ? 'テンプレート注意' : 'Template notice',
          description: res.data.warnings.join('\n'),
        })
      }
    } catch {
      toast({ title: 'テンプレートの読み込みに失敗しました', variant: 'destructive' })
    } finally {
      setIsPreviewLoading(false)
    }
  }

  const handleSubmit = async () => {
    if (!category || !subject.trim() || !message.trim()) {
      toast({ title: '必須項目を入力してください', variant: 'destructive' })
      return
    }
    setIsSubmitting(true)
    try {
      const res = await inquiriesApi.create(buildPayload())
      if (pendingFiles.length > 0) {
        await inquiriesApi.uploadAttachments(res.data.id, pendingFiles)
      }
      toast({ title: lang === 'ja' ? 'お問い合わせを送信しました' : 'Inquiry submitted' })
      router.push(`/mypage/inquiries/${res.data.id}`)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast({
        title: '送信に失敗しました',
        description: typeof detail === 'string' ? detail : undefined,
        variant: 'destructive',
      })
    } finally {
      setIsSubmitting(false)
      setShowConfirm(false)
    }
  }

  const filteredTemplates = templates.filter((tpl) => !tpl.category || tpl.category === category)

  if (!isMounted || !isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-2xl">
        <Link href="/mypage/inquiries" className="inline-flex items-center gap-2 text-gray-500 hover:text-gray-900 text-sm mb-6">
          <ArrowLeft className="h-4 w-4" />
          {lang === 'ja' ? '問い合わせ履歴' : 'Inquiry history'}
        </Link>

        <h1 className="text-2xl font-bold text-gray-900 mb-6">
          {lang === 'ja' ? 'お問い合わせ' : 'Contact us'}
        </h1>

        <div className="space-y-5">
          <div>
            <Label htmlFor="category">{lang === 'ja' ? 'カテゴリ' : 'Category'}</Label>
            <select
              id="category"
              className="mt-1 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm"
              value={category}
              onChange={(e) => {
                setCategory(e.target.value)
                setTemplateId('')
              }}
            >
              {categories.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <Label htmlFor="subject">{lang === 'ja' ? '件名' : 'Subject'}</Label>
            <Input id="subject" value={subject} onChange={(e) => setSubject(e.target.value)} className="mt-1" />
          </div>

          {filteredTemplates.length > 0 && (
            <div>
              <Label htmlFor="template">{lang === 'ja' ? '定型文（任意）' : 'Template (optional)'}</Label>
              <select
                id="template"
                className="mt-1 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm"
                value={templateId}
                onChange={(e) => void handleTemplateChange(e.target.value)}
                disabled={isPreviewLoading}
              >
                <option value="">{lang === 'ja' ? '選択しない' : 'None'}</option>
                {filteredTemplates.map((tpl) => (
                  <option key={tpl.id} value={String(tpl.id)}>
                    {tpl.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <Label htmlFor="message">{lang === 'ja' ? 'お問い合わせ内容' : 'Message'}</Label>
            <textarea
              id="message"
              rows={8}
              className="mt-1 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
            />
          </div>

          <div>
            <Label htmlFor="replyEmail">{lang === 'ja' ? '返信先メール' : 'Reply email'}</Label>
            <Input
              id="replyEmail"
              type="email"
              value={replyEmail}
              onChange={(e) => setReplyEmail(e.target.value)}
              className="mt-1"
            />
          </div>

          <div>
            <Label htmlFor="order">{lang === 'ja' ? '関連注文（任意）' : 'Related order (optional)'}</Label>
            <select
              id="order"
              className="mt-1 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm"
              value={relatedOrderId}
              onChange={(e) => setRelatedOrderId(e.target.value)}
            >
              <option value="">{lang === 'ja' ? 'なし' : 'None'}</option>
              {orders.map((o) => (
                <option key={o.id} value={String(o.id)}>
                  #{o.id} — {new Date(o.created_at).toLocaleDateString('ja-JP')}
                </option>
              ))}
            </select>
          </div>

          <div>
            <Label htmlFor="attachments">{lang === 'ja' ? '画像添付（任意）' : 'Images (optional)'}</Label>
            <input
              id="attachments"
              type="file"
              accept={INQUIRY_ACCEPTED_IMAGE_TYPES}
              multiple
              className="mt-1 block w-full text-sm text-gray-600"
              onChange={(e) => {
                const selected = Array.from(e.target.files || [])
                const err = validateInquiryFiles(selected)
                if (err) {
                  toast({ title: err, variant: 'destructive' })
                  e.target.value = ''
                  return
                }
                setPendingFiles(selected)
              }}
            />
            {pendingFiles.length > 0 && (
              <p className="text-xs text-gray-500 mt-1">
                {pendingFiles.length} {lang === 'ja' ? '件選択中' : 'file(s) selected'}
              </p>
            )}
          </div>

          <Button
            className="w-full"
            onClick={() => setShowConfirm(true)}
            disabled={isSubmitting || isPreviewLoading}
          >
            {lang === 'ja' ? '内容を確認して送信' : 'Review and submit'}
          </Button>
        </div>

        {showConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
            <div className="bg-white rounded-xl max-w-lg w-full p-6 shadow-xl">
              <h2 className="text-lg font-semibold mb-4">{lang === 'ja' ? '送信内容の確認' : 'Confirm submission'}</h2>
              <dl className="space-y-2 text-sm mb-6">
                <div>
                  <dt className="text-gray-500">{lang === 'ja' ? '件名' : 'Subject'}</dt>
                  <dd className="text-gray-900">{subject}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">{lang === 'ja' ? '内容' : 'Message'}</dt>
                  <dd className="text-gray-900 whitespace-pre-wrap max-h-40 overflow-y-auto">{message}</dd>
                </div>
              </dl>
              <div className="flex gap-3 justify-end">
                <Button variant="outline" onClick={() => setShowConfirm(false)} disabled={isSubmitting}>
                  {t('キャンセル', lang)}
                </Button>
                <Button onClick={() => void handleSubmit()} disabled={isSubmitting}>
                  {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : lang === 'ja' ? '送信する' : 'Submit'}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
