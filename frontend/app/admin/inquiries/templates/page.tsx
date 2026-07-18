'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2, Plus, Trash2 } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminInquiriesApi } from '@/lib/api'
import { InquiryTemplate } from '@/lib/types'
import { inquiryCategoryLabel } from '@/lib/inquiry-labels'
import { toast } from '@/lib/use-toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const EMPTY_FORM = {
  template_type: 'admin' as 'customer' | 'admin',
  category: '',
  name: '',
  body: '',
  is_active: true,
  sort_order: 0,
}

export default function AdminInquiryTemplatesPage() {
  const { isReady } = useAdminGuard()
  const [templates, setTemplates] = useState<InquiryTemplate[]>([])
  const [filter, setFilter] = useState<'customer' | 'admin' | ''>('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const load = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await adminInquiriesApi.manageTemplates(filter || undefined)
      setTemplates(res.data || [])
    } finally {
      setIsLoading(false)
    }
  }, [filter])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void load()
  }, [isMounted, isReady, load])

  const resetForm = () => {
    setEditingId(null)
    setForm(EMPTY_FORM)
  }

  const startEdit = (tpl: InquiryTemplate) => {
    setEditingId(tpl.id)
    setForm({
      template_type: tpl.template_type,
      category: tpl.category || '',
      name: tpl.name,
      body: tpl.body,
      is_active: tpl.is_active,
      sort_order: tpl.sort_order,
    })
  }

  const handleSave = async () => {
    if (!form.name.trim() || !form.body.trim()) {
      toast({ title: '名前と本文は必須です', variant: 'destructive' })
      return
    }
    setIsSaving(true)
    try {
      const payload = {
        ...form,
        category: form.category || null,
      }
      if (editingId) {
        await adminInquiriesApi.updateTemplate(editingId, payload)
        toast({ title: 'テンプレートを更新しました' })
      } else {
        await adminInquiriesApi.createTemplate(payload)
        toast({ title: 'テンプレートを作成しました' })
      }
      resetForm()
      await load()
    } catch {
      toast({ title: '保存に失敗しました', variant: 'destructive' })
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('このテンプレートを削除しますか？')) return
    try {
      await adminInquiriesApi.deleteTemplate(id)
      toast({ title: '削除しました' })
      if (editingId === id) resetForm()
      await load()
    } catch {
      toast({ title: '削除に失敗しました', variant: 'destructive' })
    }
  }

  if (!isMounted || !isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-5xl">
        <Link href="/admin/inquiries" className="inline-flex items-center gap-2 text-gray-500 hover:text-gray-900 text-sm mb-6">
          <ArrowLeft className="h-4 w-4" />
          問い合わせ管理
        </Link>

        <h1 className="text-2xl font-bold text-gray-900 mb-6">問い合わせ定型文</h1>

        <div className="grid lg:grid-cols-2 gap-8">
          <div>
            <div className="flex gap-2 mb-4">
              {(['', 'customer', 'admin'] as const).map((f) => (
                <button
                  key={f || 'all'}
                  type="button"
                  onClick={() => setFilter(f)}
                  className={`px-3 py-1 rounded text-sm border ${
                    filter === f ? 'border-yellow-400 bg-yellow-50 text-yellow-700' : 'border-gray-200'
                  }`}
                >
                  {f === '' ? 'すべて' : f === 'customer' ? '購入者用' : '管理者用'}
                </button>
              ))}
            </div>

            {isLoading ? (
              <div className="h-32 bg-gray-50 animate-pulse rounded" />
            ) : (
              <div className="space-y-2">
                {templates.map((tpl) => (
                  <div key={tpl.id} className="border border-gray-200 rounded-lg p-3 flex justify-between gap-2">
                    <button type="button" className="text-left flex-1" onClick={() => startEdit(tpl)}>
                      <p className="font-medium text-sm">{tpl.name}</p>
                      <p className="text-xs text-gray-500">
                        {tpl.template_type === 'customer' ? '購入者' : '管理者'}
                        {tpl.category ? ` · ${inquiryCategoryLabel(tpl.category)}` : ''}
                        {!tpl.is_active && ' · 無効'}
                      </p>
                    </button>
                    <Button variant="ghost" size="sm" onClick={() => void handleDelete(tpl.id)}>
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 space-y-4">
            <h2 className="font-medium">{editingId ? '編集' : '新規作成'}</h2>

            <div>
              <Label>種別</Label>
              <select
                className="mt-1 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm"
                value={form.template_type}
                onChange={(e) => setForm({ ...form, template_type: e.target.value as 'customer' | 'admin' })}
                disabled={!!editingId}
              >
                <option value="customer">購入者用</option>
                <option value="admin">管理者用</option>
              </select>
            </div>

            <div>
              <Label>カテゴリ（任意）</Label>
              <Input
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                placeholder="order, shipping など"
                className="mt-1"
              />
            </div>

            <div>
              <Label>名前</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1" />
            </div>

            <div>
              <Label>本文</Label>
              <textarea
                rows={10}
                className="mt-1 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm font-mono text-xs"
                value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })}
              />
            </div>

            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                />
                有効
              </label>
              <div>
                <Label className="text-xs">並び順</Label>
                <Input
                  type="number"
                  className="w-20 mt-1"
                  value={form.sort_order}
                  onChange={(e) => setForm({ ...form, sort_order: parseInt(e.target.value, 10) || 0 })}
                />
              </div>
            </div>

            <div className="flex gap-2">
              <Button onClick={() => void handleSave()} disabled={isSaving}>
                {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : editingId ? '更新' : '作成'}
              </Button>
              {editingId && (
                <Button variant="outline" onClick={resetForm}>
                  キャンセル
                </Button>
              )}
              {!editingId && (
                <Button variant="outline" onClick={() => setForm(EMPTY_FORM)}>
                  <Plus className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
