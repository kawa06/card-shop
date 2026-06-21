'use client'

import { useState, useEffect, useRef } from 'react'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { Plus, Pencil, Trash2, ArrowLeft, Upload, Images, X } from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { cardsApi, categoriesApi, adminApi, shippingApi } from '@/lib/api'
import { Card, Category, ShippingRate } from '@/lib/types'
import { usePrice } from '@/lib/format'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'
import Link from 'next/link'

const RARITIES = ['C', 'U', 'R', 'RR', 'AR', 'SR', 'SAR', 'MUR', 'SSR', 'ミラー', 'MA', 'PROMO', 'CLASSIC', 'パック', 'BOX', 'PSA10']
const CONDITIONS = ['a', 'b', 'c', 'd', 'e']
const CONDITION_LABEL: Record<string, string> = {
  a: 'A（美品）', b: 'B（良品）', c: 'C（並品）', d: 'D（傷あり）', e: 'E（難あり）'
}
const MAX_IMAGES = 10

interface CardForm {
  name: string
  name_en: string
  description: string
  price: string
  stock: string
  rarity: string
  condition: string
  category_id: string
  images: string[]  // up to 10 image URLs / data URLs
  allowed_shipping_methods: string[]
}

const emptyForm: CardForm = {
  name: '', name_en: '', description: '', price: '', stock: '',
  rarity: 'C', condition: '', category_id: '', images: [''],
  allowed_shipping_methods: [],
}

function parseImages(card: Card): string[] {
  const urls: string[] = []
  if (card.image_url) urls.push(card.image_url)
  if (card.image_urls) {
    try {
      const extra = JSON.parse(card.image_urls) as string[]
      extra.forEach(u => { if (u && !urls.includes(u)) urls.push(u) })
    } catch { /* ignore */ }
  }
  return urls.length > 0 ? urls : ['']
}

function parseShippingMethods(card: Card): string[] {
  if (!card.allowed_shipping_methods) return []
  try {
    const parsed = JSON.parse(card.allowed_shipping_methods)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export default function AdminCardsPage() {
  const router = useRouter()
  const { isAuthenticated, user, isLoading: isAuthLoading } = useAuthStore()
  const { formatPrice } = usePrice()
  const [cards, setCards] = useState<Card[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [shippingRates, setShippingRates] = useState<ShippingRate[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<CardForm>(emptyForm)
  const [saving, setSaving] = useState(false)
  const [showImagePicker, setShowImagePicker] = useState<number | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploadSlot, setUploadSlot] = useState<number>(0)
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  useEffect(() => {
    if (!isMounted || isAuthLoading) return

    if (!isAuthenticated) { router.push('/login'); return }
    if (user && !user.is_admin) { router.push('/'); return }
    fetchAll()
  }, [isMounted, isAuthLoading, isAuthenticated, user, router])

  const fetchAll = async () => {
    setIsLoading(true)
    try {
      const [cardsRes, catsRes, shipRes] = await Promise.all([
        adminApi.getAllCards({ per_page: 100 }),
        categoriesApi.getAll(),
        shippingApi.getRates(),
      ])
      const data = cardsRes.data
      setCards(Array.isArray(data) ? data : (data.items || []))
      setCategories(catsRes.data || [])
      setShippingRates(shipRes.data || [])
    } finally {
      setIsLoading(false)
    }
  }

  const handleEdit = (card: Card) => {
    setEditingId(card.id)
    setForm({
      name: card.name,
      name_en: card.name_en || '',
      description: card.description || '',
      price: card.price.toString(),
      stock: card.stock.toString(),
      rarity: card.rarity || 'C',
      condition: card.condition || '',
      category_id: card.category_id?.toString() || '',
      images: parseImages(card),
      allowed_shipping_methods: parseShippingMethods(card),
    })
    setShowForm(true)
  }

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`「${name}」を削除しますか？`)) return
    try {
      await adminApi.deleteCard(id)
      toast({ title: '削除しました' })
      fetchAll()
    } catch {
      toast({ title: 'エラー', description: '削除に失敗しました', variant: 'destructive' })
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    const validImages = form.images.filter(u => u.trim() !== '')
    const image_url = validImages[0] || null
    const extra = validImages.slice(1)
    const data = {
      name: form.name,
      name_en: form.name_en || null,
      description: form.description,
      price: parseFloat(form.price),
      stock: parseInt(form.stock),
      rarity: form.rarity,
      condition: form.condition || null,
      category_id: form.category_id ? parseInt(form.category_id) : null,
      image_url,
      image_urls: extra.length > 0 ? JSON.stringify(extra) : null,
      allowed_shipping_methods: form.allowed_shipping_methods.length > 0 ? JSON.stringify(form.allowed_shipping_methods) : null,
    }
    try {
      if (editingId) {
        await adminApi.updateCard(editingId, data)
        toast({ title: '更新しました' })
      } else {
        await adminApi.createCard(data)
        toast({ title: '作成しました' })
      }
      setShowForm(false)
      setEditingId(null)
      setForm(emptyForm)
      fetchAll()
    } catch {
      toast({ title: 'エラー', description: '保存に失敗しました', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  const toggleShippingMethod = (code: string) => {
    setForm(f => {
      const current = f.allowed_shipping_methods
      if (current.includes(code)) {
        return { ...f, allowed_shipping_methods: current.filter(c => c !== code) }
      } else {
        return { ...f, allowed_shipping_methods: [...current, code] }
      }
    })
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 5 * 1024 * 1024) {
      toast({ title: 'エラー', description: '5MB以下の画像を選択してください', variant: 'destructive' })
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      setForm(f => {
        const imgs = [...f.images]
        imgs[uploadSlot] = reader.result as string
        return { ...f, images: imgs }
      })
    }
    reader.readAsDataURL(file)
    e.target.value = ''
  }

  const setImageAt = (idx: number, val: string) => {
    setForm(f => {
      const imgs = [...f.images]
      imgs[idx] = val
      return { ...f, images: imgs }
    })
  }

  const removeImageAt = (idx: number) => {
    setForm(f => {
      const imgs = f.images.filter((_, i) => i !== idx)
      return { ...f, images: imgs.length > 0 ? imgs : [''] }
    })
  }

  const addImageSlot = () => {
    if (form.images.length >= MAX_IMAGES) return
    setForm(f => ({ ...f, images: [...f.images, ''] }))
  }

  const existingImages = cards.filter(c => c.image_url && !c.image_url.startsWith('data:'))

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="container py-8 max-w-5xl">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/admin">
            <Button variant="ghost" size="icon" className="text-gray-400 hover:text-white">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <h1 className="text-2xl font-bold text-white flex-1">カード管理</h1>
          <Button
            onClick={() => { setShowForm(true); setEditingId(null); setForm(emptyForm) }}
            className="bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold"
          >
            <Plus className="h-4 w-4 mr-1" />新規追加
          </Button>
        </div>

        {/* フォーム */}
        {showForm && (
          <div className="bg-gray-900 rounded-xl border border-white/10 p-6 mb-6">
            <h2 className="text-white font-semibold mb-4">
              {editingId ? 'カードを編集' : '新規カード作成'}
            </h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* カード名 */}
                <div className="space-y-1">
                  <Label className="text-gray-300">カード名 *</Label>
                  <Input value={form.name} onChange={e => setForm({...form, name: e.target.value})} required className="bg-gray-800 border-gray-700 text-white" />
                </div>

                {/* 英語名 */}
                <div className="space-y-1">
                  <Label className="text-gray-300">英語名</Label>
                  <Input value={form.name_en} onChange={e => setForm({...form, name_en: e.target.value})} className="bg-gray-800 border-gray-700 text-white" />
                </div>

                {/* レアリティ */}
                <div className="space-y-1">
                  <Label className="text-gray-300">レアリティ *</Label>
                  <select value={form.rarity} onChange={e => setForm({...form, rarity: e.target.value})} className="w-full h-10 rounded-md border border-gray-700 bg-gray-800 px-3 text-white text-sm">
                    {RARITIES.map(r => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>

                {/* 価格 */}
                <div className="space-y-1">
                  <Label className="text-gray-300">価格 *</Label>
                  <Input type="number" value={form.price} onChange={e => setForm({...form, price: e.target.value})} required min="0" className="bg-gray-800 border-gray-700 text-white" />
                </div>

                {/* 在庫 */}
                <div className="space-y-1">
                  <Label className="text-gray-300">在庫数 *</Label>
                  <Input type="number" value={form.stock} onChange={e => setForm({...form, stock: e.target.value})} required min="0" className="bg-gray-800 border-gray-700 text-white" />
                </div>

                {/* 状態 */}
                <div className="space-y-1">
                  <Label className="text-gray-300">状態</Label>
                  <select value={form.condition} onChange={e => setForm({...form, condition: e.target.value})} className="w-full h-10 rounded-md border border-gray-700 bg-gray-800 px-3 text-white text-sm">
                    <option value="">-- 選択 --</option>
                    {CONDITIONS.map(c => <option key={c} value={c}>{CONDITION_LABEL[c]}</option>)}
                  </select>
                </div>

                {/* カテゴリー */}
                <div className="space-y-1">
                  <Label className="text-gray-300">カテゴリー</Label>
                  <select value={form.category_id} onChange={e => setForm({...form, category_id: e.target.value})} className="w-full h-10 rounded-md border border-gray-700 bg-gray-800 px-3 text-white text-sm">
                    <option value="">-- 選択 --</option>
                    {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>

                {/* 説明 */}
                <div className="sm:col-span-2 space-y-1">
                  <Label className="text-gray-300">説明</Label>
                  <textarea value={form.description} onChange={e => setForm({...form, description: e.target.value})} rows={2} className="w-full rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white resize-none" />
                </div>

                {/* 発送方法制限 */}
                <div className="sm:col-span-2 space-y-2 pt-2 border-t border-white/5">
                  <Label className="text-gray-300">許可する発送方法</Label>
                  <p className="text-[10px] text-gray-500 mb-2">指定しない場合は全ての発送方法が選択可能 / 例: 高額カードは宅急便コンパクトのみに制限</p>
                  
                  <div className="space-y-4">
                    {Object.entries(
                      shippingRates.reduce((acc, rate) => {
                        const carrier = rate.carrier || 'other'
                        if (!acc[carrier]) acc[carrier] = []
                        acc[carrier].push(rate)
                        return acc
                      }, {} as Record<string, ShippingRate[]>)
                    ).map(([carrier, rates]) => (
                      <div key={carrier} className="space-y-2">
                        <h3 className="text-[10px] uppercase tracking-wider text-gray-500 font-bold ml-1">
                          {carrier === 'yamato' ? 'ヤマト運輸' : carrier === 'japan_post' ? '日本郵便' : 'その他'}
                        </h3>
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                          {rates.map(rate => (
                            <label key={rate.method_code} className="flex items-center gap-2 cursor-pointer group p-2 rounded bg-gray-800/50 border border-white/5 hover:border-white/10 transition-colors">
                              <input
                                type="checkbox"
                                checked={form.allowed_shipping_methods.includes(rate.method_code)}
                                onChange={() => toggleShippingMethod(rate.method_code)}
                                className="w-4 h-4 rounded border-gray-700 bg-gray-800 text-yellow-400 focus:ring-yellow-400"
                              />
                              <span className="text-[11px] text-gray-400 group-hover:text-white transition-colors">{rate.name_ja}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* 画像スロット (最大10枚) */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label className="text-gray-300">画像（最大{MAX_IMAGES}枚）</Label>
                  <span className="text-xs text-gray-500">{form.images.filter(u => u).length}/{MAX_IMAGES}枚</span>
                </div>
                <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileChange} />

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {form.images.map((url, idx) => (
                    <div key={idx} className="space-y-1">
                      <div className="relative">
                        {/* プレビュー or プレースホルダー */}
                        {url ? (
                          <div className="relative aspect-[3/4] rounded-lg overflow-hidden border border-white/10 bg-gray-800">
                            <Image src={url} alt={`画像 ${idx + 1}`} fill className="object-cover" unoptimized={url.startsWith('data:')} />
                            <button type="button" onClick={() => removeImageAt(idx)} className="absolute top-1 right-1 bg-red-600/80 hover:bg-red-600 rounded-full p-0.5">
                              <X className="h-3 w-3 text-white" />
                            </button>
                          </div>
                        ) : (
                          <div className="aspect-[3/4] rounded-lg border-2 border-dashed border-white/20 bg-gray-800/50 flex flex-col items-center justify-center gap-2 text-gray-500 text-xs">
                            <span>画像 {idx + 1}</span>
                          </div>
                        )}
                      </div>
                      <div className="flex gap-1">
                        <Input
                          value={url.startsWith('data:') ? '' : url}
                          onChange={e => setImageAt(idx, e.target.value)}
                          placeholder="URL"
                          className="bg-gray-800 border-gray-700 text-white text-xs h-7 flex-1"
                        />
                        <Button type="button" variant="outline" size="icon" className="h-7 w-7 border-gray-700 text-gray-400 hover:text-white hover:bg-gray-700 shrink-0"
                          onClick={() => { setUploadSlot(idx); fileInputRef.current?.click() }} title="ファイルを選択">
                          <Upload className="h-3 w-3" />
                        </Button>
                        {existingImages.length > 0 && (
                          <Button type="button" variant="outline" size="icon" className="h-7 w-7 border-gray-700 text-gray-400 hover:text-white hover:bg-gray-700 shrink-0"
                            onClick={() => setShowImagePicker(idx)} title="既存画像から選ぶ">
                            <Images className="h-3 w-3" />
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}

                  {/* 追加ボタン */}
                  {form.images.length < MAX_IMAGES && (
                    <button type="button" onClick={addImageSlot}
                      className="aspect-[3/4] rounded-lg border-2 border-dashed border-white/20 hover:border-yellow-400/50 bg-gray-800/30 flex flex-col items-center justify-center gap-1 text-gray-500 hover:text-yellow-400 transition-colors text-xs">
                      <Plus className="h-5 w-5" />
                      <span>追加</span>
                    </button>
                  )}
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <Button type="submit" disabled={saving} className="bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold">
                  {saving ? '保存中...' : editingId ? '更新' : '作成'}
                </Button>
                <Button type="button" variant="ghost" onClick={() => { setShowForm(false); setEditingId(null) }} className="text-gray-400">
                  キャンセル
                </Button>
              </div>
            </form>
          </div>
        )}

        {/* 既存画像ピッカー モーダル */}
        {showImagePicker !== null && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={() => setShowImagePicker(null)}>
            <div className="bg-gray-900 rounded-xl border border-white/10 p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-white font-semibold">既存の画像から選択</h3>
                <Button variant="ghost" size="icon" onClick={() => setShowImagePicker(null)} className="text-gray-400 hover:text-white">
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <div className="grid grid-cols-4 sm:grid-cols-6 gap-3">
                {existingImages.map(card => (
                  <button key={card.id} type="button"
                    onClick={() => {
                      setImageAt(showImagePicker, card.image_url!)
                      setShowImagePicker(null)
                    }}
                    className="group relative aspect-[2/3] rounded-md overflow-hidden border-2 border-transparent hover:border-yellow-400 transition-all bg-gray-800"
                    title={card.name}
                  >
                    <Image src={card.image_url!} alt={card.name} fill className="object-cover" />
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-all" />
                    <div className="absolute bottom-0 left-0 right-0 bg-black/70 px-1 py-0.5 text-xs text-white truncate opacity-0 group-hover:opacity-100 transition-all">
                      {card.name}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* テーブル */}
        <div className="bg-gray-900 rounded-xl border border-white/10 overflow-hidden">
          {isLoading ? (
            <div className="p-8 text-center text-gray-400 animate-pulse">読み込み中...</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-white/10">
                  <tr>
                    <th className="text-left text-gray-400 font-medium px-4 py-3">カード</th>
                    <th className="text-left text-gray-400 font-medium px-4 py-3">レアリティ</th>
                    <th className="text-left text-gray-400 font-medium px-4 py-3">状態</th>
                    <th className="text-left text-gray-400 font-medium px-4 py-3">ステータス</th>
                    <th className="text-right text-gray-400 font-medium px-4 py-3">価格</th>
                    <th className="text-right text-gray-400 font-medium px-4 py-3">在庫</th>
                    <th className="text-right text-gray-400 font-medium px-4 py-3">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {cards.map((card) => (
                    <tr key={card.id} className={`border-b border-white/5 hover:bg-white/5 ${!card.is_active ? 'opacity-50 bg-black/20' : ''}`}>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="relative w-8 h-10 rounded overflow-hidden bg-gray-800 flex-shrink-0">
                            {card.image_url ? (
                              <Image src={card.image_url} alt={card.name} fill className="object-cover" unoptimized={card.image_url.startsWith('data:')} />
                            ) : (
                              <div className="flex items-center justify-center h-full text-sm">🃏</div>
                            )}
                          </div>
                          <div className="flex flex-col">
                            <span className="text-white font-medium">{card.name}</span>
                            {card.name_en && <span className="text-gray-500 text-[10px]">{card.name_en}</span>}
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-400">{card.rarity}</td>
                      <td className="px-4 py-3 text-gray-400">{card.condition ? CONDITION_LABEL[card.condition] ?? card.condition : '—'}</td>
                      <td className="px-4 py-3">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded border ${card.is_active ? 'bg-green-500/10 text-green-400 border-green-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'}`}>
                          {card.is_active ? '公開中' : '非公開'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right text-yellow-400">{formatPrice(card.price)}</td>
                      <td className="px-4 py-3 text-right text-gray-400">{card.stock}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end gap-2">
                          <Button variant="ghost" size="icon" onClick={() => handleEdit(card)} className="h-8 w-8 text-blue-400 hover:text-blue-300">
                            <Pencil className="h-3 w-3" />
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => handleDelete(card.id, card.name)} className="h-8 w-8 text-red-400 hover:text-red-300">
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </td>
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
