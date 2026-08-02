'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
  ArrowLeft,
  Bell,
  Eye,
  GripVertical,
  Plus,
  Save,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { announcementsApi } from '@/lib/api'
import { AnnouncementAdmin } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'
import AnnouncementRichEditor from '@/components/announcements/AnnouncementRichEditor'
import AnnouncementHtml from '@/components/announcements/AnnouncementHtml'
import { translateJaToEn } from '@/lib/translate'

type AdminFormState = Pick<
  import('@/lib/types').AnnouncementFormData,
  'title_ja' | 'content_ja' | 'status' | 'publish_at' | 'expire_at' | 'thumbnail' | 'priority' | 'image_urls'
>

const EMPTY_FORM: AdminFormState = {
  title_ja: '',
  content_ja: '',
  status: 'draft',
  publish_at: null,
  expire_at: null,
  thumbnail: null,
  priority: 0,
  image_urls: [],
}

function toLocalInput(iso: string | null | undefined): string | null {
  if (!iso) return null
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function toIsoOrNull(value: string | null | undefined) {
  if (!value || !value.trim()) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

function statusLabel(status: string) {
  if (status === 'published') return '公開中'
  if (status === 'scheduled') return '公開予約'
  return '下書き'
}

export default function AdminAnnouncementsPage() {
  const { isReady } = useAdminGuard()
  const [announcements, setAnnouncements] = useState<AnnouncementAdmin[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<AdminFormState>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [search, setSearch] = useState('')
  const [previewLang, setPreviewLang] = useState<'ja' | 'en'>('ja')
  const [showPreview, setShowPreview] = useState(false)
  const [previewEn, setPreviewEn] = useState({ title: '', content: '' })
  const [previewLoading, setPreviewLoading] = useState(false)

  const fetchAnnouncements = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await announcementsApi.adminGetAll(search.trim() || undefined)
      setAnnouncements(res.data || [])
    } finally {
      setIsLoading(false)
    }
  }, [search])

  useEffect(() => {
    if (isReady) fetchAnnouncements()
  }, [isReady, fetchAnnouncements])

  const openCreate = () => {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setShowForm(true)
  }

  const openEdit = (row: AnnouncementAdmin) => {
    setEditingId(row.id)
    setForm({
      title_ja: row.title_ja,
      content_ja: row.content_ja,
      status: row.status,
      publish_at: toLocalInput(row.publish_at) || null,
      expire_at: toLocalInput(row.expire_at) || null,
      thumbnail: row.thumbnail || null,
      priority: row.priority || 0,
      image_urls: (row.images || []).map((img) => img.image_url),
    })
    setShowForm(true)
  }

  useEffect(() => {
    if (!showPreview || previewLang !== 'en') return
    let cancelled = false
    setPreviewLoading(true)
    translateJaToEn([form.title_ja, form.content_ja])
      .then(([title, content]) => {
        if (!cancelled) setPreviewEn({ title, content })
      })
      .catch(() => {
        if (!cancelled) setPreviewEn({ title: form.title_ja, content: form.content_ja })
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [showPreview, previewLang, form.title_ja, form.content_ja])

  const uploadImage = async (file: File) => {
    const res = await announcementsApi.uploadImage(file)
    return res.data.url
  }

  const handleThumbnailUpload = async (file: File) => {
    try {
      const url = await uploadImage(file)
      setForm((prev) => ({ ...prev, thumbnail: url }))
    } catch {
      toast({ title: '画像アップロードに失敗しました', variant: 'destructive' })
    }
  }

  const handleGalleryUpload = async (file: File) => {
    try {
      const url = await uploadImage(file)
      setForm((prev) => ({ ...prev, image_urls: [...prev.image_urls, url] }))
    } catch {
      toast({ title: '画像アップロードに失敗しました', variant: 'destructive' })
    }
  }

  const validateForm = () => {
    if (!form.title_ja.trim()) {
      toast({ title: 'タイトルを入力してください', variant: 'destructive' })
      return false
    }
    const plainJa = form.content_ja.replace(/<[^>]+>/g, '').trim()
    if (!plainJa) {
      toast({ title: '本文を入力してください', variant: 'destructive' })
      return false
    }
    if (form.status === 'scheduled' && !form.publish_at) {
      toast({ title: '公開予約には公開日時が必要です', variant: 'destructive' })
      return false
    }
    return true
  }

  const buildPayload = () => ({
    title_ja: form.title_ja.trim(),
    content_ja: form.content_ja,
    status: form.status,
    publish_at: toIsoOrNull(form.publish_at),
    expire_at: toIsoOrNull(form.expire_at),
    clear_publish_at: !form.publish_at,
    clear_expire_at: !form.expire_at,
    thumbnail: form.thumbnail || null,
    priority: form.priority,
    image_urls: form.image_urls,
    title: form.title_ja.trim(),
    content: form.content_ja,
    is_active: form.status === 'published',
  })

  const handleSubmit = async (nextStatus?: AdminFormState['status']) => {
    if (!validateForm()) return
    setSaving(true)
    try {
      const payload = buildPayload()
      if (nextStatus) payload.status = nextStatus
      if (editingId) {
        await announcementsApi.update(editingId, payload)
        toast({ title: '更新しました' })
      } else {
        await announcementsApi.create(payload)
        toast({ title: '作成しました' })
      }
      setShowForm(false)
      setEditingId(null)
      setForm(EMPTY_FORM)
      fetchAnnouncements()
    } catch {
      toast({ title: '保存に失敗しました', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('このお知らせを削除しますか？')) return
    try {
      await announcementsApi.delete(id)
      toast({ title: '削除しました' })
      if (editingId === id) {
        setShowForm(false)
        setEditingId(null)
      }
      fetchAnnouncements()
    } catch {
      toast({ title: '削除に失敗しました', variant: 'destructive' })
    }
  }

  const preview = useMemo(() => {
    if (previewLang === 'ja') {
      return { title: form.title_ja, content: form.content_ja }
    }
    return previewEn
  }, [form.title_ja, form.content_ja, previewLang, previewEn])

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-5xl">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/admin">
            <Button variant="ghost" size="icon" className="text-gray-400 hover:text-gray-900">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <Bell className="h-6 w-6 text-purple-400" />
          <h1 className="text-2xl font-bold text-gray-900 flex-1">お知らせ管理</h1>
          <Button onClick={openCreate} className="bg-purple-600 text-white hover:bg-purple-500 font-bold">
            <Plus className="h-4 w-4 mr-1" />
            新規作成
          </Button>
        </div>

        <div className="mb-6">
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="タイトル・本文で検索"
            className="max-w-md bg-gray-50"
          />
        </div>

        {showForm && (
          <div className="bg-gray-50 rounded-xl border border-gray-200 p-6 mb-8 space-y-5">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-gray-900 font-semibold">{editingId ? 'お知らせを編集' : '新規お知らせ'}</h2>
              <div className="flex gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setShowPreview(true)}>
                  <Eye className="h-4 w-4 mr-1" /> プレビュー
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setShowForm(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <p className="text-sm text-gray-500">
              日本語のみ入力してください。英語は保存時・プレビュー時に自動翻訳されます。
            </p>

            <div className="space-y-1">
              <Label>タイトル</Label>
              <Input value={form.title_ja} onChange={(e) => setForm({ ...form, title_ja: e.target.value })} />
            </div>

            <AnnouncementRichEditor
              key={`content-${editingId ?? 'new'}`}
              label="本文"
              value={form.content_ja}
              onChange={(html) => setForm({ ...form, content_ja: html })}
              onUploadImage={uploadImage}
            />

            <div className="grid md:grid-cols-3 gap-4">
              <div className="space-y-1">
                <Label>ステータス</Label>
                <select
                  className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
                  value={form.status}
                  onChange={(e) => setForm({ ...form, status: e.target.value as AdminFormState['status'] })}
                >
                  <option value="draft">下書き</option>
                  <option value="published">公開</option>
                  <option value="scheduled">公開予約</option>
                </select>
              </div>
              <div className="space-y-1">
                <Label>公開日時</Label>
                <Input type="datetime-local" value={form.publish_at || ''} onChange={(e) => setForm({ ...form, publish_at: e.target.value || null })} />
              </div>
              <div className="space-y-1">
                <Label>公開終了日時</Label>
                <Input type="datetime-local" value={form.expire_at || ''} onChange={(e) => setForm({ ...form, expire_at: e.target.value || null })} />
              </div>
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>サムネイル（共通）</Label>
                {form.thumbnail && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={form.thumbnail} alt="" className="h-24 rounded border object-cover" />
                )}
                <label className="inline-flex items-center gap-2 text-sm text-purple-600 cursor-pointer">
                  <Upload className="h-4 w-4" />
                  画像をアップロード
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) handleThumbnailUpload(file)
                    }}
                  />
                </label>
              </div>
              <div className="space-y-1">
                <Label>並び順（大きいほど上）</Label>
                <Input
                  type="number"
                  value={form.priority}
                  onChange={(e) => setForm({ ...form, priority: Number(e.target.value) || 0 })}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>ギャラリー画像（複数）</Label>
              <div className="flex flex-wrap gap-2">
                {form.image_urls.map((url, index) => (
                  <div key={`${url}-${index}`} className="relative">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={url} alt="" className="h-20 w-20 object-cover rounded border" />
                    <button
                      type="button"
                      className="absolute -top-2 -right-2 bg-white border rounded-full p-0.5"
                      onClick={() =>
                        setForm({
                          ...form,
                          image_urls: form.image_urls.filter((_, i) => i !== index),
                        })
                      }
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
              <label className="inline-flex items-center gap-2 text-sm text-purple-600 cursor-pointer">
                <Upload className="h-4 w-4" />
                ギャラリーに追加
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) handleGalleryUpload(file)
                  }}
                />
              </label>
            </div>

            <div className="flex flex-wrap gap-2 pt-2">
              <Button disabled={saving} onClick={() => handleSubmit()} className="bg-purple-600 hover:bg-purple-500">
                <Save className="h-4 w-4 mr-1" />
                {saving ? '保存中...' : '保存'}
              </Button>
              <Button disabled={saving} variant="outline" onClick={() => handleSubmit('draft')}>
                下書き保存
              </Button>
              <Button disabled={saving} variant="outline" onClick={() => handleSubmit('published')}>
                公開
              </Button>
            </div>
          </div>
        )}

        <div className="bg-gray-50 rounded-xl border border-gray-200 overflow-hidden">
          {isLoading ? (
            <div className="p-8 text-center text-gray-400 animate-pulse">読み込み中...</div>
          ) : announcements.length === 0 ? (
            <div className="p-8 text-center text-gray-500">お知らせはありません</div>
          ) : (
            <div className="divide-y divide-gray-100">
              {announcements.map((row) => (
                <div key={row.id} className="p-4 flex items-start gap-3 hover:bg-gray-100/70">
                  <GripVertical className="h-5 w-5 text-gray-300 mt-1 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <h3 className="font-medium text-gray-900 truncate">{row.title_ja}</h3>
                      <span className="text-[10px] px-2 py-0.5 rounded border bg-white text-gray-600">
                        {statusLabel(row.status)}
                      </span>
                      <span className="text-[10px] text-gray-400">優先 {row.priority || 0}</span>
                    </div>
                    <p className="text-sm text-gray-500 truncate">{row.title_en}</p>
                    <p className="text-[10px] text-gray-400">英語（自動翻訳）</p>
                    <p className="text-xs text-gray-400 mt-1">
                      更新: {row.updated_at ? new Date(row.updated_at).toLocaleString('ja-JP') : '—'}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => openEdit(row)}>
                      編集
                    </Button>
                    <Button variant="ghost" size="sm" className="text-red-500" onClick={() => handleDelete(row.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {showPreview && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={() => setShowPreview(false)}>
          <div className="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex gap-2">
                <Button size="sm" variant={previewLang === 'ja' ? 'default' : 'outline'} onClick={() => setPreviewLang('ja')}>日本語</Button>
                <Button size="sm" variant={previewLang === 'en' ? 'default' : 'outline'} onClick={() => setPreviewLang('en')}>English</Button>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setShowPreview(false)}><X className="h-4 w-4" /></Button>
            </div>
            <h2 className="text-2xl font-bold mb-4">
              {previewLoading && previewLang === 'en' ? '翻訳中...' : preview.title || '（タイトル未入力）'}
            </h2>
            {previewLoading && previewLang === 'en' ? (
              <p className="text-gray-400 animate-pulse">English preview loading...</p>
            ) : (
              <AnnouncementHtml html={preview.content || '<p>（本文未入力）</p>'} />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
