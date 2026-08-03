'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2, Mail, Plus } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminEmailApi } from '@/lib/api'
import { toast } from '@/lib/use-toast'

const CATEGORIES = [
  { id: 'member', label: '会員登録' },
  { id: 'login', label: 'ログイン' },
  { id: 'password', label: 'パスワード' },
  { id: 'security', label: 'セキュリティ' },
  { id: 'point', label: 'ポイント' },
  { id: 'coupon', label: 'クーポン' },
  { id: 'rank', label: '会員ランク' },
  { id: 'campaign', label: 'キャンペーン' },
  { id: 'other', label: 'その他' },
  { id: 'notice', label: 'お知らせ' },
  { id: 'promo', label: 'キャンペーン配信' },
  { id: 'broadcast', label: '配信その他' },
  { id: 'inquiry', label: 'お問い合わせ' },
  { id: 'order', label: '購入' },
  { id: 'shipping', label: '発送・配送' },
  { id: 'buyback', label: '買取' },
  { id: 'kyc', label: '本人確認・保護者同意' },
  { id: 'ops', label: '運営' },
]

type TemplateItem = {
  id: number
  template_key: string
  category: string
  name: string
  subject: string
  is_active: boolean
}

export default function AdminEmailPage() {
  const { isReady } = useAdminGuard()
  const [category, setCategory] = useState('member')
  const [templates, setTemplates] = useState<TemplateItem[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)

  const handleCreateBuybackTemplate = async () => {
    const key = window.prompt('テンプレートキー（例: buyback_custom_notice）')
    if (!key) return
    const name = window.prompt('テンプレート名') || key
    setCreating(true)
    try {
      await adminEmailApi.createTemplate({
        template_key: key,
        category: 'buyback',
        name,
        subject: '【{{shopName}}】（件名を入力）（{{buyNo}}）',
        preheader: '（プリヘッダーを入力）',
        html_body: `<p style="margin:0 0 20px;font-size:15px;color:#475569;">{{name}} 様</p>
<h1 style="margin:0 0 12px;font-size:20px;font-weight:600;color:#0f172a;">{{bodyTitle}}</h1>
<p style="margin:0 0 24px;font-size:15px;line-height:1.75;color:#475569;">{{bodyDescription}}</p>
{{buybackInfoBlock}}
{{itemsTable}}
{{buttonsBlock}}
{{notesBlock}}
{{contactBlock}}
{{signatureBlock}}`,
        text_body: '{{name}} 様\\n\\n{{bodyTitle}}\\n\\n{{bodyDescription}}',
        is_active: false,
      })
      toast({ title: 'テンプレートを作成しました' })
      void load()
    } catch {
      toast({ title: 'テンプレートの作成に失敗しました', variant: 'destructive' })
    } finally {
      setCreating(false)
    }
  }

  const handleCreateShippingTemplate = async () => {
    const key = window.prompt('テンプレートキー（例: shipping_custom_notice）')
    if (!key) return
    const name = window.prompt('テンプレート名') || key
    setCreating(true)
    try {
      await adminEmailApi.createTemplate({
        template_key: key,
        category: 'shipping',
        name,
        subject: '【{{shopName}}】（件名を入力）（{{orderNo}}）',
        preheader: '（プリヘッダーを入力）',
        html_body: `<p style="margin:0 0 20px;font-size:15px;color:#475569;">{{name}} 様</p>
<h1 style="margin:0 0 12px;font-size:20px;font-weight:600;color:#0f172a;">{{bodyTitle}}</h1>
<p style="margin:0 0 24px;font-size:15px;line-height:1.75;color:#475569;">{{bodyDescription}}</p>
{{shippingInfoBlock}}
{{buttonsBlock}}
{{notesBlock}}
{{contactBlock}}
{{signatureBlock}}`,
        text_body: '{{name}} 様\\n\\n{{bodyTitle}}\\n\\n{{bodyDescription}}',
        is_active: false,
      })
      toast({ title: 'テンプレートを作成しました' })
      void load()
    } catch {
      toast({ title: 'テンプレートの作成に失敗しました', variant: 'destructive' })
    } finally {
      setCreating(false)
    }
  }

  const handleCreateKycTemplate = async () => {
    const key = window.prompt('テンプレートキー（例: kyc_custom_notice）')
    if (!key) return
    const name = window.prompt('テンプレート名') || key
    setCreating(true)
    try {
      await adminEmailApi.createTemplate({
        template_key: key,
        category: 'kyc',
        name,
        subject: '【{{shopName}}】（件名を入力）（{{authNo}}）',
        preheader: '（プリヘッダーを入力）',
        html_body: `<p style="margin:0 0 20px;font-size:15px;color:#475569;">{{name}} 様</p>
<h1 style="margin:0 0 12px;font-size:20px;font-weight:600;color:#0f172a;">{{bodyTitle}}</h1>
<p style="margin:0 0 24px;font-size:15px;line-height:1.75;color:#475569;">{{bodyDescription}}</p>
{{kycInfoBlock}}
{{buttonsBlock}}
{{notesBlock}}
{{contactBlock}}
{{signatureBlock}}`,
        text_body: '{{name}} 様\\n\\n{{bodyTitle}}\\n\\n{{bodyDescription}}',
        is_active: false,
      })
      toast({ title: 'テンプレートを作成しました' })
      void load()
    } catch {
      toast({ title: 'テンプレートの作成に失敗しました', variant: 'destructive' })
    } finally {
      setCreating(false)
    }
  }

  const handleCreateBroadcastTemplate = async (category: string) => {
    const prefix = category === 'notice' ? 'broadcast_notice_' : category === 'promo' ? 'broadcast_promo_' : 'broadcast_'
    const key = window.prompt(`テンプレートキー（例: ${prefix}custom_notice）`)
    if (!key) return
    const name = window.prompt('テンプレート名') || key
    setCreating(true)
    try {
      await adminEmailApi.createTemplate({
        template_key: key,
        category,
        name,
        subject: '【{{shopName}}】（件名を入力）',
        preheader: '（プリヘッダーを入力）',
        html_body: `<p style="margin:0 0 20px;font-size:15px;color:#475569;">{{name}} 様</p>
<h1 style="margin:0 0 12px;font-size:20px;font-weight:600;color:#0f172a;">{{bodyTitle}}</h1>
<p style="margin:0 0 24px;font-size:15px;line-height:1.75;color:#475569;">{{bodyDescription}}</p>
{{broadcastInfoBlock}}
{{imageBlock}}
<div style="margin:0 0 24px;font-size:15px;line-height:1.75;color:#475569;">{{noticeContent}}</div>
{{buttonsBlock}}
{{notesBlock}}
{{contactBlock}}
{{signatureBlock}}`,
        text_body: '{{name}} 様\\n\\n{{bodyTitle}}\\n\\n{{bodyDescription}}',
        is_active: false,
      })
      toast({ title: 'テンプレートを作成しました' })
      void load()
    } catch {
      toast({ title: 'テンプレートの作成に失敗しました', variant: 'destructive' })
    } finally {
      setCreating(false)
    }
  }

  const handleCreateInquiryTemplate = async () => {
    const key = window.prompt('テンプレートキー（例: inquiry_custom_notice）')
    if (!key) return
    const name = window.prompt('テンプレート名') || key
    setCreating(true)
    try {
      await adminEmailApi.createTemplate({
        template_key: key,
        category: 'inquiry',
        name,
        subject: '【{{shopName}}】（件名を入力）',
        preheader: '（プリヘッダーを入力）',
        html_body: `<p style="margin:0 0 20px;font-size:15px;color:#475569;">{{name}} 様</p>
<h1 style="margin:0 0 12px;font-size:20px;font-weight:600;color:#0f172a;">{{bodyTitle}}</h1>
<p style="margin:0 0 24px;font-size:15px;line-height:1.75;color:#475569;">{{bodyDescription}}</p>
{{inquiryInfoBlock}}
{{attachmentBlock}}
<div style="margin:0 0 24px;font-size:15px;line-height:1.75;color:#475569;">{{replyContent}}</div>
{{buttonsBlock}}
{{notesBlock}}
{{contactBlock}}
{{signatureBlock}}`,
        text_body: '{{name}} 様\\n\\n{{bodyTitle}}\\n\\n{{bodyDescription}}',
        is_active: false,
      })
      toast({ title: 'テンプレートを作成しました' })
      void load()
    } catch {
      toast({ title: 'テンプレートの作成に失敗しました', variant: 'destructive' })
    } finally {
      setCreating(false)
    }
  }

  const handleCreateLoyaltyTemplate = async (category: string) => {
    const prefixMap: Record<string, string> = {
      point: 'point_',
      coupon: 'coupon_',
      rank: 'rank_',
      campaign: 'campaign_',
      other: 'loyalty_',
    }
    const prefix = prefixMap[category] || 'point_'
    const key = window.prompt(`テンプレートキー（例: ${prefix}custom_notice）`)
    if (!key) return
    const name = window.prompt('テンプレート名') || key
    setCreating(true)
    try {
      await adminEmailApi.createTemplate({
        template_key: key,
        category,
        name,
        subject: '【{{shopName}}】（件名を入力）',
        preheader: '（プリヘッダーを入力）',
        html_body: `<p style="margin:0 0 20px;font-size:15px;color:#475569;">{{name}} 様</p>
<h1 style="margin:0 0 12px;font-size:20px;font-weight:600;color:#0f172a;">{{bodyTitle}}</h1>
<p style="margin:0 0 24px;font-size:15px;line-height:1.75;color:#475569;">{{bodyDescription}}</p>
{{loyaltyInfoBlock}}
{{buttonsBlock}}
{{notesBlock}}
{{contactBlock}}
{{signatureBlock}}`,
        text_body: '{{name}} 様\\n\\n{{bodyTitle}}\\n\\n{{bodyDescription}}',
        is_active: false,
      })
      toast({ title: 'テンプレートを作成しました' })
      void load()
    } catch {
      toast({ title: 'テンプレートの作成に失敗しました', variant: 'destructive' })
    } finally {
      setCreating(false)
    }
  }

  const handleCreateMemberTemplate = async (category: string) => {
    const prefix = category === 'member' ? 'member_' : category === 'login' ? 'login_' : category === 'password' ? 'password_' : 'security_'
    const key = window.prompt(`テンプレートキー（例: ${prefix}custom_notice）`)
    if (!key) return
    const name = window.prompt('テンプレート名') || key
    setCreating(true)
    try {
      await adminEmailApi.createTemplate({
        template_key: key,
        category,
        name,
        subject: '【{{shopName}}】（件名を入力）',
        preheader: '（プリヘッダーを入力）',
        html_body: `<p style="margin:0 0 20px;font-size:15px;color:#475569;">{{name}} 様</p>
<h1 style="margin:0 0 12px;font-size:20px;font-weight:600;color:#0f172a;">{{bodyTitle}}</h1>
<p style="margin:0 0 24px;font-size:15px;line-height:1.75;color:#475569;">{{bodyDescription}}</p>
{{memberInfoBlock}}
{{buttonsBlock}}
{{notesBlock}}
{{contactBlock}}
{{signatureBlock}}`,
        text_body: '{{name}} 様\\n\\n{{bodyTitle}}\\n\\n{{bodyDescription}}',
        is_active: false,
      })
      toast({ title: 'テンプレートを作成しました' })
      void load()
    } catch {
      toast({ title: 'テンプレートの作成に失敗しました', variant: 'destructive' })
    } finally {
      setCreating(false)
    }
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await adminEmailApi.listTemplates(category)
      setTemplates(res.data)
    } catch {
      toast({ title: 'テンプレート一覧の取得に失敗しました', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [category])

  useEffect(() => {
    if (isReady) void load()
  }, [isReady, load])

  if (!isReady) return null

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link href="/admin" className="text-gray-500 hover:text-gray-900">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Mail className="h-6 w-6" /> メールテンプレート管理
          </h1>
        </div>
        <div className="flex gap-3 text-sm">
          {category === 'shipping' && (
            <button
              type="button"
              onClick={() => void handleCreateShippingTemplate()}
              disabled={creating}
              className="inline-flex items-center gap-1 text-emerald-600 hover:underline disabled:opacity-50"
            >
              <Plus className="h-4 w-4" /> 新規テンプレート
            </button>
          )}
          {(category === 'member' || category === 'login' || category === 'password' || category === 'security') && (
            <>
              <Link href="/admin/settings/email/member-notifications" className="text-purple-600 hover:underline">
                自動送信設定
              </Link>
              <button
                type="button"
                onClick={() => void handleCreateMemberTemplate(category)}
                disabled={creating}
                className="inline-flex items-center gap-1 text-emerald-600 hover:underline disabled:opacity-50"
              >
                <Plus className="h-4 w-4" /> 新規テンプレート
              </button>
            </>
          )}
          {category === 'buyback' && (
            <>
              <Link href="/admin/settings/email/buyback-notifications" className="text-purple-600 hover:underline">
                自動送信設定
              </Link>
              <button
                type="button"
                onClick={() => void handleCreateBuybackTemplate()}
                disabled={creating}
                className="inline-flex items-center gap-1 text-emerald-600 hover:underline disabled:opacity-50"
              >
                <Plus className="h-4 w-4" /> 新規テンプレート
              </button>
            </>
          )}
          {category === 'kyc' && (
            <>
              <Link href="/admin/settings/email/kyc-notifications" className="text-purple-600 hover:underline">
                自動送信設定
              </Link>
              <button
                type="button"
                onClick={() => void handleCreateKycTemplate()}
                disabled={creating}
                className="inline-flex items-center gap-1 text-emerald-600 hover:underline disabled:opacity-50"
              >
                <Plus className="h-4 w-4" /> 新規テンプレート
              </button>
            </>
          )}
          {(category === 'notice' || category === 'promo' || category === 'broadcast') && (
            <>
              <button
                type="button"
                onClick={() => void handleCreateBroadcastTemplate(category)}
                disabled={creating}
                className="inline-flex items-center gap-1 text-emerald-600 hover:underline disabled:opacity-50"
              >
                <Plus className="h-4 w-4" /> 新規テンプレート
              </button>
            </>
          )}
          {(category === 'point' || category === 'coupon' || category === 'rank' || category === 'campaign') && (
            <>
              <Link href="/admin/settings/email/loyalty-notifications" className="text-purple-600 hover:underline">
                自動送信設定
              </Link>
              <button
                type="button"
                onClick={() => void handleCreateLoyaltyTemplate(category)}
                disabled={creating}
                className="inline-flex items-center gap-1 text-emerald-600 hover:underline disabled:opacity-50"
              >
                <Plus className="h-4 w-4" /> 新規テンプレート
              </button>
            </>
          )}
          {category === 'inquiry' && (
            <>
              <Link href="/admin/settings/email/inquiry-notifications" className="text-purple-600 hover:underline">
                自動送信設定
              </Link>
              <button
                type="button"
                onClick={() => void handleCreateInquiryTemplate()}
                disabled={creating}
                className="inline-flex items-center gap-1 text-emerald-600 hover:underline disabled:opacity-50"
              >
                <Plus className="h-4 w-4" /> 新規テンプレート
              </button>
            </>
          )}
          {category === 'other' && (
            <button
              type="button"
              onClick={() => void handleCreateLoyaltyTemplate(category)}
              disabled={creating}
              className="inline-flex items-center gap-1 text-emerald-600 hover:underline disabled:opacity-50"
            >
              <Plus className="h-4 w-4" /> 新規テンプレート
            </button>
          )}
          <Link href="/admin/settings/email/brand" className="text-cyan-600 hover:underline">
            ブランド設定
          </Link>
          <Link href="/admin/settings/email/logs" className="text-yellow-600 hover:underline">
            送信履歴
          </Link>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-6">
        {CATEGORIES.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => setCategory(c.id)}
            className={`px-3 py-1.5 rounded-full text-sm border ${
              category === c.id
                ? 'bg-yellow-400 border-yellow-400 text-gray-950 font-medium'
                : 'bg-white border-gray-200 text-gray-600'
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      ) : (
        <div className="space-y-2">
          {templates.map((t) => (
            <Link
              key={t.template_key}
              href={`/admin/settings/email/${encodeURIComponent(t.template_key)}`}
              className="block rounded-lg border border-gray-200 bg-white p-4 hover:border-yellow-400/50 transition-colors"
            >
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="font-medium text-gray-900">{t.name}</p>
                  <p className="text-xs text-gray-500">{t.template_key}</p>
                  <p className="text-sm text-gray-600 mt-1 truncate">{t.subject}</p>
                </div>
                <span
                  className={`text-xs px-2 py-1 rounded ${
                    t.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                  }`}
                >
                  {t.is_active ? '有効' : '無効'}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
