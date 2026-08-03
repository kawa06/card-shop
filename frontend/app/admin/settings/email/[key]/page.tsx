'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { ArrowLeft, Eye, Loader2, Monitor, Moon, Send, Smartphone } from 'lucide-react'
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
  preheader?: string | null
  html_body: string
  text_body?: string | null
  variables_hint?: string | null
  is_active: boolean
}

export default function AdminEmailEditPage() {
  const params = useParams()
  const key = decodeURIComponent(String(params.key || ''))
  const { isReady } = useAdminGuard()
  const [tpl, setTpl] = useState<Template | null>(null)
  const [previewHtml, setPreviewHtml] = useState('')
  const [previewSubject, setPreviewSubject] = useState('')
  const [previewPreheader, setPreviewPreheader] = useState('')
  const [previewMode, setPreviewMode] = useState<'desktop' | 'mobile' | 'dark'>('desktop')
  const [variablesInfo, setVariablesInfo] = useState<{
    variables: string[]
    aliases: Record<string, string>
    sample: Record<string, string>
  } | null>(null)
  const [testEmail, setTestEmail] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [tplRes, varRes] = await Promise.all([
        adminEmailApi.getTemplate(key),
        adminEmailApi.getTemplateVariables(key),
      ])
      setTpl(tplRes.data)
      setVariablesInfo(varRes.data)
    } catch {
      toast({ title: 'テンプレートの取得に失敗しました', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [key])

  useEffect(() => {
    if (isReady && key) void load()
  }, [isReady, key, load])

  const refreshPreview = useCallback(async () => {
    if (!tpl) return
    setPreviewLoading(true)
    try {
      const res = await adminEmailApi.previewTemplate(key, {
        variables: variablesInfo?.sample,
        subject: tpl.subject,
        preheader: tpl.preheader || '',
        html_body: tpl.html_body,
        text_body: tpl.text_body || '',
        force_dark: previewMode === 'dark',
      })
      setPreviewHtml(res.data.html)
      setPreviewSubject(res.data.subject)
      setPreviewPreheader(res.data.preheader || '')
    } catch {
      setPreviewHtml('')
    } finally {
      setPreviewLoading(false)
    }
  }, [key, tpl, variablesInfo?.sample, previewMode])

  useEffect(() => {
    if (tpl) {
      const timer = setTimeout(() => void refreshPreview(), 400)
      return () => clearTimeout(timer)
    }
  }, [tpl?.subject, tpl?.preheader, tpl?.html_body, tpl?.text_body, previewMode, refreshPreview, tpl])

  const aliasList = useMemo(() => {
    if (!variablesInfo) return []
    const entries = Object.entries(variablesInfo.aliases)
    return entries.slice(0, 12)
  }, [variablesInfo])

  const handleSave = async () => {
    if (!tpl) return
    setSaving(true)
    try {
      const res = await adminEmailApi.updateTemplate(key, {
        name: tpl.name,
        subject: tpl.subject,
        preheader: tpl.preheader,
        html_body: tpl.html_body,
        text_body: tpl.text_body,
        is_active: tpl.is_active,
      })
      setTpl(res.data)
      toast({ title: '保存しました' })
    } catch {
      toast({ title: '保存に失敗しました', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  const handleTestSend = async () => {
    if (!testEmail) return
    try {
      await adminEmailApi.testSend(key, testEmail, variablesInfo?.sample || {})
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

  const previewWidth = previewMode === 'mobile' ? '375px' : '100%'
  const previewFrameClass =
    previewMode === 'dark'
      ? 'bg-slate-900 border-slate-700 shadow-sm rounded-lg'
      : 'bg-white border shadow-sm rounded-lg'

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl">
      <Link href="/admin/settings/email" className="inline-flex items-center gap-2 text-gray-500 mb-4">
        <ArrowLeft className="h-4 w-4" /> 一覧に戻る
      </Link>
      <h1 className="text-xl font-bold mb-1">{tpl.name}</h1>
      <p className="text-sm text-gray-500 mb-6">{tpl.template_key}</p>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div>
            <Label htmlFor="name">テンプレート名</Label>
            <Input
              id="name"
              value={tpl.name}
              onChange={(e) => setTpl({ ...tpl, name: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="subject">件名</Label>
            <Input
              id="subject"
              value={tpl.subject}
              onChange={(e) => setTpl({ ...tpl, subject: e.target.value })}
            />
          </div>
        <div>
          <Label htmlFor="preheader">プリヘッダー</Label>
          <Input
            id="preheader"
            value={tpl.preheader || ''}
            onChange={(e) => setTpl({ ...tpl, preheader: e.target.value })}
            placeholder="受信トレイで件名の横に表示される短いテキスト"
          />
        </div>
        <div>
          <Label htmlFor="html">HTML本文</Label>
            <textarea
              id="html"
              className="w-full min-h-[320px] rounded-md border border-gray-200 p-3 font-mono text-sm"
              value={tpl.html_body}
              onChange={(e) => setTpl({ ...tpl, html_body: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="text">テキスト本文</Label>
            <textarea
              id="text"
              className="w-full min-h-[120px] rounded-md border border-gray-200 p-3 font-mono text-sm"
              value={tpl.text_body || ''}
              onChange={(e) => setTpl({ ...tpl, text_body: e.target.value })}
            />
          </div>

          {variablesInfo && (
            <div className="rounded-lg border bg-gray-50 p-3 text-xs space-y-2">
              <p className="font-medium text-gray-700">使用可能な変数（プレビューはサンプル値で表示）</p>
              <div className="flex flex-wrap gap-1">
                {variablesInfo.variables.map((v) => (
                  <code key={v} className="bg-white border px-1.5 py-0.5 rounded">{`{{${v}}}`}</code>
                ))}
              </div>
              {aliasList.length > 0 && (
                <div className="flex flex-wrap gap-1 pt-1">
                  {aliasList.map(([ja, en]) => (
                    <code key={ja} className="bg-purple-50 border border-purple-100 px-1.5 py-0.5 rounded text-purple-700">{`{{${ja}}}`}</code>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <Button onClick={handleSave} disabled={saving}>
              {saving ? '保存中…' : '保存'}
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
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-semibold flex items-center gap-2">
              <Eye className="h-4 w-4" /> メールプレビュー
            </h2>
            <div className="flex gap-1">
              <Button
                size="sm"
                variant={previewMode === 'desktop' ? 'default' : 'outline'}
                onClick={() => setPreviewMode('desktop')}
              >
                <Monitor className="h-3 w-3 mr-1" /> PC
              </Button>
              <Button
                size="sm"
                variant={previewMode === 'mobile' ? 'default' : 'outline'}
                onClick={() => setPreviewMode('mobile')}
              >
                <Smartphone className="h-3 w-3 mr-1" /> スマホ
              </Button>
              <Button
                size="sm"
                variant={previewMode === 'dark' ? 'default' : 'outline'}
                onClick={() => setPreviewMode('dark')}
              >
                <Moon className="h-3 w-3 mr-1" /> ダーク
              </Button>
            </div>
          </div>
          <p className="text-xs text-gray-500 mb-2">
            件名: {previewSubject || '—'}
            {previewPreheader && ` / プリヘッダー: ${previewPreheader}`}
          </p>
          <div
            className={`border rounded-lg overflow-hidden flex justify-center p-4 min-h-[480px] ${
              previewMode === 'dark' ? 'bg-slate-950' : 'bg-gray-100'
            }`}
          >
            {previewLoading ? (
              <Loader2 className="h-6 w-6 animate-spin text-gray-400 mt-20" />
            ) : previewHtml ? (
              <iframe
                title="preview"
                srcDoc={previewHtml}
                style={{ width: previewWidth, maxWidth: '100%', height: '520px' }}
                className={previewFrameClass}
                sandbox=""
              />
            ) : (
              <p className="text-gray-400 text-sm mt-20">プレビューを読み込み中…</p>
            )}
          </div>
          <p className="text-xs text-gray-400 mt-2">保存前でも編集内容がリアルタイムで反映されます</p>
        </div>
      </div>
    </div>
  )
}
