'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Plus, Pencil, Trash2, Upload } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminApi, adminBuybackApi } from '@/lib/api'
import type { AdminBuybackCatalogProduct, AdminBuybackCatalogProductInput } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'
import { compressImageFile } from '@/lib/image-compress'

const CATEGORIES = ['raw', 'graded', 'sealed', 'accessory']

interface PriceFormRow {
  condition_code: string
  price_normal: string
  price_high: string
  purchase_limit: string
  tier_overflow_price: string
}

interface ProductForm {
  name: string
  category: string
  card_number: string
  rarity: string
  pack_name: string
  image_url: string
  notes: string
  is_active: boolean
  sort_order: string
  prices: PriceFormRow[]
}

const emptyPriceRow = (): PriceFormRow => ({
  condition_code: 'default',
  price_normal: '',
  price_high: '',
  purchase_limit: '',
  tier_overflow_price: '',
})

const emptyForm = (): ProductForm => ({
  name: '',
  category: 'raw',
  card_number: '',
  rarity: '',
  pack_name: '',
  image_url: '',
  notes: '',
  is_active: true,
  sort_order: '0',
  prices: [emptyPriceRow()],
})

function parseOptionalInt(value: string): number | null {
  const trimmed = value.trim()
  if (!trimmed) return null
  const parsed = Number.parseInt(trimmed, 10)
  return Number.isNaN(parsed) ? null : parsed
}

function toPayload(form: ProductForm): AdminBuybackCatalogProductInput | null {
  const priceNormal = parseOptionalInt(form.prices[0]?.price_normal ?? '')
  if (priceNormal === null || priceNormal < 0) return null

  return {
    name: form.name.trim(),
    category: form.category.trim(),
    card_number: form.card_number.trim() || null,
    rarity: form.rarity.trim() || null,
    pack_name: form.pack_name.trim() || null,
    image_url: form.image_url.trim() || null,
    notes: form.notes.trim() || null,
    is_active: form.is_active,
    sort_order: parseOptionalInt(form.sort_order) ?? 0,
    prices: form.prices.map((row) => {
      const normal = parseOptionalInt(row.price_normal)
      if (normal === null || normal < 0) {
        throw new Error('invalid price')
      }
      return {
        condition_code: row.condition_code.trim() || 'default',
        price_normal: normal,
        price_high: parseOptionalInt(row.price_high),
        purchase_limit: parseOptionalInt(row.purchase_limit),
        tier_overflow_price: parseOptionalInt(row.tier_overflow_price),
      }
    }),
  }
}

function productToForm(product: AdminBuybackCatalogProduct): ProductForm {
  return {
    name: product.name,
    category: product.category,
    card_number: product.card_number || '',
    rarity: product.rarity || '',
    pack_name: product.pack_name || '',
    image_url: product.image_url || '',
    notes: product.notes || '',
    is_active: product.is_active,
    sort_order: String(product.sort_order ?? 0),
    prices:
      product.prices.length > 0
        ? product.prices.map((price) => ({
            condition_code: price.condition_code,
            price_normal: String(price.price_normal),
            price_high: price.price_high != null ? String(price.price_high) : '',
            purchase_limit:
              price.purchase_limit != null ? String(price.purchase_limit) : '',
            tier_overflow_price:
              price.tier_overflow_price != null
                ? String(price.tier_overflow_price)
                : '',
          }))
        : [emptyPriceRow()],
  }
}

export default function AdminBuybackCatalogPage() {
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const canWrite = hasPermission('buyback.catalog.write')
  const [items, setItems] = useState<AdminBuybackCatalogProduct[]>([])
  const [includeInactive, setIncludeInactive] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isMounted, setIsMounted] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<ProductForm>(emptyForm())
  const [saving, setSaving] = useState(false)
  const [uploadingImage, setUploadingImage] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const fetchAll = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await adminBuybackApi.listCatalogProducts({
        include_inactive: includeInactive,
      })
      setItems(res.data || [])
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data
        ?.detail
      toast({
        title: '読み込みに失敗しました',
        description: typeof detail === 'string' ? detail : '買取カタログの取得に失敗しました',
        variant: 'destructive',
      })
    } finally {
      setIsLoading(false)
    }
  }, [includeInactive])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void fetchAll()
  }, [isMounted, isReady, fetchAll])

  const getApiErrorMessage = (err: unknown, fallback: string) => {
    const detail = (err as { response?: { data?: { detail?: string | { msg?: string }[] } } })
      ?.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg
    return fallback
  }

  const handleEdit = (product: AdminBuybackCatalogProduct) => {
    setEditingId(product.id)
    setForm(productToForm(product))
    setShowForm(true)
  }

  const handleDelete = async (product: AdminBuybackCatalogProduct) => {
    if (!canWrite) return
    if (!confirm(`「${product.name}」を非公開にしますか？`)) return
    try {
      await adminBuybackApi.deleteCatalogProduct(product.id)
      toast({ title: '非公開にしました' })
      void fetchAll()
    } catch (err) {
      toast({
        title: 'エラー',
        description: getApiErrorMessage(err, '削除に失敗しました'),
        variant: 'destructive',
      })
    }
  }

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadingImage(true)
    try {
      const compressed = await compressImageFile(file)
      const res = await adminApi.uploadImage(compressed, compressed.name)
      setForm((current) => ({ ...current, image_url: res.data.url }))
      toast({ title: '画像をアップロードしました' })
    } catch (err) {
      toast({
        title: 'エラー',
        description: getApiErrorMessage(err, '画像のアップロードに失敗しました'),
        variant: 'destructive',
      })
    } finally {
      setUploadingImage(false)
      e.target.value = ''
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canWrite) return
    setSaving(true)
    let payload: AdminBuybackCatalogProductInput | null = null
    try {
      payload = toPayload(form)
    } catch {
      payload = null
    }
    if (!payload || !payload.name || !payload.category) {
      toast({
        title: 'エラー',
        description: '必須項目と価格を確認してください',
        variant: 'destructive',
      })
      setSaving(false)
      return
    }

    try {
      const res = editingId
        ? await adminBuybackApi.updateCatalogProduct(editingId, payload)
        : await adminBuybackApi.createCatalogProduct(payload)
      setItems((current) => {
        const next = current.filter((item) => item.id !== res.data.id)
        if (res.data.is_active || includeInactive) {
          next.unshift(res.data)
        }
        return next.sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)
      })
      toast({ title: editingId ? '更新しました' : '登録しました' })
      setShowForm(false)
      setEditingId(null)
      setForm(emptyForm())
    } catch (err) {
      toast({
        title: 'エラー',
        description: getApiErrorMessage(err, '保存に失敗しました'),
        variant: 'destructive',
      })
    } finally {
      setSaving(false)
    }
  }

  if (!isMounted || !isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-6xl">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <Link href="/admin" className="text-gray-500 hover:text-gray-900">
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">買取カタログ管理</h1>
          </div>
          {canWrite && (
            <Button
              onClick={() => {
                setShowForm(true)
                setEditingId(null)
                setForm(emptyForm())
              }}
              className="bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold"
            >
              <Plus className="h-4 w-4 mr-1" />
              新規追加
            </Button>
          )}
        </div>

        <div className="flex items-center gap-3 mb-4">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(e) => setIncludeInactive(e.target.checked)}
            />
            非公開を含める
          </label>
        </div>

        {showForm && canWrite && (
          <div className="bg-gray-50 rounded-xl border border-gray-200 p-6 mb-6">
            <h2 className="font-semibold mb-4">
              {editingId ? '買取カードを編集' : '買取カードを新規登録'}
            </h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label>カード名 *</Label>
                  <Input
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-1">
                  <Label>カテゴリー *</Label>
                  <select
                    value={form.category}
                    onChange={(e) => setForm({ ...form, category: e.target.value })}
                    className="w-full h-10 rounded-md border border-gray-300 bg-white px-3 text-sm"
                  >
                    {CATEGORIES.map((category) => (
                      <option key={category} value={category}>
                        {category}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <Label>カード番号</Label>
                  <Input
                    value={form.card_number}
                    onChange={(e) => setForm({ ...form, card_number: e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <Label>レアリティ</Label>
                  <Input
                    value={form.rarity}
                    onChange={(e) => setForm({ ...form, rarity: e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <Label>収録パック</Label>
                  <Input
                    value={form.pack_name}
                    onChange={(e) => setForm({ ...form, pack_name: e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <Label>並び順</Label>
                  <Input
                    type="number"
                    value={form.sort_order}
                    onChange={(e) => setForm({ ...form, sort_order: e.target.value })}
                  />
                </div>
                <div className="space-y-1 sm:col-span-2">
                  <Label>画像URL</Label>
                  <div className="flex gap-2">
                    <Input
                      value={form.image_url}
                      onChange={(e) => setForm({ ...form, image_url: e.target.value })}
                      placeholder="アップロード成功後に自動入力"
                    />
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={handleImageUpload}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      disabled={uploadingImage}
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <Upload className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div className="space-y-1 sm:col-span-2">
                  <Label>備考</Label>
                  <textarea
                    value={form.notes}
                    onChange={(e) => setForm({ ...form, notes: e.target.value })}
                    rows={2}
                    className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
                  />
                </div>
              </div>

              <div className="border-t border-gray-200 pt-4 space-y-3">
                <h3 className="font-medium text-sm">状態別価格 *</h3>
                {form.prices.map((row, index) => (
                  <div key={index} className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                    <Input
                      value={row.condition_code}
                      onChange={(e) => {
                        const prices = [...form.prices]
                        prices[index] = { ...prices[index], condition_code: e.target.value }
                        setForm({ ...form, prices })
                      }}
                      placeholder="状態コード"
                    />
                    <Input
                      type="number"
                      min="0"
                      value={row.price_normal}
                      onChange={(e) => {
                        const prices = [...form.prices]
                        prices[index] = { ...prices[index], price_normal: e.target.value }
                        setForm({ ...form, prices })
                      }}
                      placeholder="通常買取"
                      required
                    />
                    <Input
                      type="number"
                      min="0"
                      value={row.price_high}
                      onChange={(e) => {
                        const prices = [...form.prices]
                        prices[index] = { ...prices[index], price_high: e.target.value }
                        setForm({ ...form, prices })
                      }}
                      placeholder="高価買取"
                    />
                    <Input
                      type="number"
                      min="0"
                      value={row.purchase_limit}
                      onChange={(e) => {
                        const prices = [...form.prices]
                        prices[index] = { ...prices[index], purchase_limit: e.target.value }
                        setForm({ ...form, prices })
                      }}
                      placeholder="上限枚数"
                    />
                    <Input
                      type="number"
                      min="0"
                      value={row.tier_overflow_price}
                      onChange={(e) => {
                        const prices = [...form.prices]
                        prices[index] = {
                          ...prices[index],
                          tier_overflow_price: e.target.value,
                        }
                        setForm({ ...form, prices })
                      }}
                      placeholder="上限超過後"
                    />
                  </div>
                ))}
              </div>

              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                />
                公開する
              </label>

              <div className="flex gap-3">
                <Button type="submit" disabled={saving || uploadingImage}>
                  {saving ? '保存中...' : editingId ? '更新' : '登録'}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setShowForm(false)
                    setEditingId(null)
                  }}
                >
                  キャンセル
                </Button>
              </div>
            </form>
          </div>
        )}

        <div className="bg-gray-50 rounded-xl border border-gray-200 overflow-hidden">
          {isLoading ? (
            <div className="p-8 text-center text-gray-400 animate-pulse">読み込み中...</div>
          ) : items.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              買取対象カードがまだ登録されていません。
              {canWrite ? ' 右上の「新規追加」から登録できます。' : ''}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-gray-200">
                  <tr>
                    <th className="text-left px-4 py-3">カード</th>
                    <th className="text-left px-4 py-3">カテゴリー</th>
                    <th className="text-left px-4 py-3">パック</th>
                    <th className="text-right px-4 py-3">通常買取</th>
                    <th className="text-left px-4 py-3">状態</th>
                    {canWrite && <th className="text-right px-4 py-3">操作</th>}
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id} className="border-b border-gray-100">
                      <td className="px-4 py-3">
                        <div className="font-medium text-gray-900">{item.name}</div>
                        <div className="text-xs text-gray-500">
                          {[item.card_number, item.rarity].filter(Boolean).join(' · ') || '—'}
                        </div>
                      </td>
                      <td className="px-4 py-3">{item.category}</td>
                      <td className="px-4 py-3">{item.pack_name || '—'}</td>
                      <td className="px-4 py-3 text-right">
                        ¥{(item.prices[0]?.price_normal ?? 0).toLocaleString()}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-xs px-2 py-0.5 rounded ${
                            item.is_active
                              ? 'bg-green-100 text-green-700'
                              : 'bg-gray-200 text-gray-600'
                          }`}
                        >
                          {item.is_active ? '公開中' : '非公開'}
                        </span>
                      </td>
                      {canWrite && (
                        <td className="px-4 py-3 text-right">
                          <div className="flex justify-end gap-2">
                            <Button variant="ghost" size="icon" onClick={() => handleEdit(item)}>
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => void handleDelete(item)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
