'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2, Plus, Pencil, Trash2 } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminBuybackApi } from '@/lib/api'
import type { BuybackPromoBanner } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'
import { extractApiErrorDetail, localInputToIso, toLocalInputValue } from '@/lib/buyback-datetime'

const emptyForm = (): {
  title: string
  description: string
  target_channel: BuybackPromoBanner['target_channel']
  starts_at: string
  ends_at: string
  background_color: string
  text_color: string
  sort_order: number
  is_visible: boolean
} => ({
  title: '',
  description: '',
  target_channel: 'both',
  starts_at: '',
  ends_at: '',
  background_color: '#1a1a2e',
  text_color: '#ffffff',
  sort_order: 0,
  is_visible: true,
})

export default function AdminBuybackBannersPage() {
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const canWrite = hasPermission('buyback.settings.write')
  const [banners, setBanners] = useState<BuybackPromoBanner[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState(emptyForm())
  const [isSaving, setIsSaving] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await adminBuybackApi.listBanners()
      setBanners(res.data)
    } catch {
      toast({ title: 'バナー一覧の取得に失敗しました', variant: 'destructive' })
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isReady) void load()
  }, [isReady, load])

  const openCreate = () => {
    setEditingId(null)
    setForm(emptyForm())
  }

  const openEdit = (banner: BuybackPromoBanner) => {
    setEditingId(banner.id)
    setForm({
      title: banner.title,
      description: banner.description || '',
      target_channel: banner.target_channel,
      starts_at: toLocalInputValue(banner.starts_at),
      ends_at: toLocalInputValue(banner.ends_at),
      background_color: banner.background_color,
      text_color: banner.text_color,
      sort_order: banner.sort_order,
      is_visible: banner.is_visible,
    })
  }

  const handleSave = async () => {
    if (!canWrite) return
    setIsSaving(true)
    try {
      const payload = {
        ...form,
        starts_at: localInputToIso(form.starts_at),
        ends_at: localInputToIso(form.ends_at),
        description: form.description.trim() || null,
      }
      if (editingId) {
        await adminBuybackApi.updateBanner(editingId, payload)
        toast({ title: 'バナーを更新しました' })
      } else {
        await adminBuybackApi.createBanner(payload)
        toast({ title: 'バナーを追加しました' })
      }
      openCreate()
      await load()
    } catch (err: unknown) {
      const detail = extractApiErrorDetail(err)
      toast({
        title: '保存に失敗しました',
        description: detail,
        variant: 'destructive',
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!canWrite || !confirm('このバナーを削除しますか？')) return
    try {
      await adminBuybackApi.deleteBanner(id)
      toast({ title: 'バナーを削除しました' })
      await load()
    } catch {
      toast({ title: '削除に失敗しました', variant: 'destructive' })
    }
  }

  if (!isReady) return null

  return (
    <div className="mx-auto max-w-5xl space-y-8 p-4 md:p-8">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link href="/admin" className="text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold">限定価格バナー</h1>
            <p className="text-sm text-muted-foreground">買取ページ上部に表示するキャンペーンバナー</p>
          </div>
        </div>
        {canWrite && (
          <Button variant="outline" onClick={openCreate}>
            <Plus className="mr-2 h-4 w-4" />
            新規
          </Button>
        )}
      </div>

      {canWrite && (
        <section className="space-y-4 rounded-xl border bg-card p-6">
          <h2 className="font-semibold">{editingId ? 'バナー編集' : 'バナー追加'}</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2 md:col-span-2">
              <Label>タイトル</Label>
              <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label>説明文</Label>
              <textarea
                className="min-h-[80px] w-full rounded-md border bg-background px-3 py-2"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>対象</Label>
              <select
                className="w-full rounded-md border bg-background px-3 py-2"
                value={form.target_channel}
                onChange={(e) =>
                  setForm({ ...form, target_channel: e.target.value as BuybackPromoBanner['target_channel'] })
                }
              >
                <option value="both">両方</option>
                <option value="store">店舗買取</option>
                <option value="mail">郵送買取</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label>表示順</Label>
              <Input
                type="number"
                value={form.sort_order}
                onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) })}
              />
            </div>
            <div className="space-y-2">
              <Label>開始日時</Label>
              <Input
                type="datetime-local"
                value={form.starts_at}
                onChange={(e) => setForm({ ...form, starts_at: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>終了日時</Label>
              <Input
                type="datetime-local"
                value={form.ends_at}
                onChange={(e) => setForm({ ...form, ends_at: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>背景色</Label>
              <Input
                type="color"
                value={form.background_color}
                onChange={(e) => setForm({ ...form, background_color: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>文字色</Label>
              <Input
                type="color"
                value={form.text_color}
                onChange={(e) => setForm({ ...form, text_color: e.target.value })}
              />
            </div>
            <label className="flex items-center gap-2 md:col-span-2">
              <input
                type="checkbox"
                checked={form.is_visible}
                onChange={(e) => setForm({ ...form, is_visible: e.target.checked })}
              />
              表示する
            </label>
          </div>
          <div
            className="rounded-xl p-5 text-center shadow-lg"
            style={{ backgroundColor: form.background_color, color: form.text_color }}
          >
            <p className="text-lg font-bold">{form.title || 'プレビュー'}</p>
            {form.description && <p className="mt-2 text-sm opacity-90">{form.description}</p>}
          </div>
          <Button onClick={() => void handleSave()} disabled={isSaving || !form.title || !form.starts_at || !form.ends_at}>
            {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {editingId ? '更新' : '追加'}
          </Button>
        </section>
      )}

      <section className="space-y-3">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : banners.length === 0 ? (
          <p className="text-muted-foreground">バナーがありません</p>
        ) : (
          banners.map((banner) => (
            <article key={banner.id} className="rounded-xl border bg-card p-4">
              <div
                className="mb-3 rounded-lg p-4 text-center"
                style={{ backgroundColor: banner.background_color, color: banner.text_color }}
              >
                <p className="font-bold">{banner.title}</p>
                {banner.description && <p className="mt-1 text-sm">{banner.description}</p>}
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
                <span>
                  {banner.target_channel} · 順序 {banner.sort_order} ·{' '}
                  {banner.is_active ? '開催中' : banner.is_visible ? '期間外' : '非表示'}
                </span>
                {canWrite && (
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => openEdit(banner)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => void handleDelete(banner.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </div>
            </article>
          ))
        )}
      </section>
    </div>
  )
}
