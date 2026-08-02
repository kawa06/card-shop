'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { ArrowLeft, Eye, Loader2, Send } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminEmailApi } from '@/lib/api'
import { toast } from '@/lib/use-toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

type Template = {
  template_key: string
  name: string
  subject: string
  html_body: string
  variables_hint?: string | null
  is_active: boolean
}

export default function AdminEmailEditPage() {
  const params = useParams()
  const key = decodeURIComponent(String(params.key || ''))
  const { isReady } = useAdminGuard()
  const [tpl, setTpl] = useState<Template | null>(null)
  const [previewHtml, setPreviewHtml] = useState('')
  const [testEmail, setTestEmail] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await adminEmailApi.getTemplate(key)
      setTpl(res.data)
    } catch {
      toast({ title: 'テンプレートの取得に失敗しました', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [key])

  useEffect(() => {
    if (isReady && key) void load()
  }, [isReady, key, load])

  const handleSave = async () => {
    if (!tpl) return
    setSaving(true)
    try {
      const res = await adminEmailApi.updateTemplate(key, {
        name: tpl.name,
        subject: tpl.subject,
        html_body: tpl.html_body,
      })
      setTpl(res.data)
      toast({ title: '保存しました' })
    } catch {
      toast({ title: '保存に失敗しました', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  const handlePreview = async () => {
    try {
      const res = await adminEmailApi.previewTemplate(key, {
        name: 'テスト太郎',
        email: 'test@example.com',
        shopName: 'KRX TCG',
      })
      setPreviewHtml(res.data.html)
    } catch {
      toast({ title: 'プレビューに失敗しました', variant: 'destructive' })
    }
  }

  const handleTestSend = async () => {
    if (!testEmail) return
    try {
      await adminEmailApi.testSend(key, testEmail, { name: 'テスト太郎', email: testEmail })
      toast({ title: 'テストメールを送信しました' })
    } catch {
      toast({ title: 'テスト送信に失敗しました', variant: 'destructive' })
    }
  }

  if (!isReady || loading || !tpl) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <Link href="/admin/settings/email" className="inline-flex items-center gap-2 text-gray-500 mb-4">
        <ArrowLeft className="h-4 w-4" /> 一覧に戻る
      </Link>
      <h1 className="text-xl font-bold mb-1">{tpl.name}</h1>
      <p className="text-sm text-gray-500 mb-6">{tpl.template_key}</p>

      <div className="space-y-4 mb-6">
        <div>
          <Label htmlFor="subject">件名</Label>
          <Input
            id="subject"
            value={tpl.subject}
            onChange={(e) => setTpl({ ...tpl, subject: e.target.value })}
          />
        </div>
        <div>
          <Label htmlFor="html">HTML本文</Label>
          <textarea
            id="html"
            className="w-full min-h-[280px] rounded-md border border-gray-200 p-3 font-mono text-sm"
            value={tpl.html_body}
            onChange={(e) => setTpl({ ...tpl, html_body: e.target.value })}
          />
          {tpl.variables_hint && (
            <p className="text-xs text-gray-500 mt-1">変数: {tpl.variables_hint}</p>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-8">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? '保存中…' : '保存'}
        </Button>
        <Button variant="outline" onClick={handlePreview}>
          <Eye className="h-4 w-4 mr-1" /> プレビュー
        </Button>
        <Input
          placeholder="テスト送信先メール"
          value={testEmail}
          onChange={(e) => setTestEmail(e.target.value)}
          className="max-w-xs"
        />
        <Button variant="outline" onClick={handleTestSend}>
          <Send className="h-4 w-4 mr-1" /> テスト送信
        </Button>
      </div>

      {previewHtml && (
        <div className="border rounded-lg overflow-hidden">
          <p className="text-xs bg-gray-100 px-3 py-2 text-gray-600">プレビュー</p>
          <iframe title="preview" srcDoc={previewHtml} className="w-full h-[480px] bg-white" sandbox="" />
        </div>
      )}
    </div>
  )
}
