'use client'

import { useState, useEffect } from 'react'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { Plus, Pencil, Trash2, ArrowLeft } from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { cardsApi, categoriesApi, adminApi } from '@/lib/api'
import { Card, Category } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'
import Link from 'next/link'

interface CardForm {
  name: string
  description: string
  price: string
  stock: string
  rarity: string
  category_id: string
  image_url: string
}

const emptyForm: CardForm = {
  name: '',
  description: '',
  price: '',
  stock: '',
  rarity: 'N',
  category_id: '',
  image_url: '',
}

export default function AdminCardsPage() {
  const router = useRouter()
  const { isAuthenticated, user } = useAuthStore()
  const [cards, setCards] = useState<Card[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<CardForm>(emptyForm)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!isAuthenticated) { router.push('/login'); return }
    if (user && !user.is_admin) { router.push('/'); return }
    fetchAll()
  }, [isAuthenticated, user, router])

  const fetchAll = async () => {
    setIsLoading(true)
    try {
      const [cardsRes, catsRes] = await Promise.all([
        cardsApi.getAll({ size: 100 }),
        categoriesApi.getAll(),
      ])
      const data = cardsRes.data
      setCards(Array.isArray(data) ? data : (data.items || []))
      setCategories(catsRes.data || [])
    } finally {
      setIsLoading(false)
    }
  }

  const handleEdit = (card: Card) => {
    setEditingId(card.id)
    setForm({
      name: card.name,
      description: card.description || '',
      price: card.price.toString(),
      stock: card.stock.toString(),
      rarity: card.rarity,
      category_id: card.category_id?.toString() || '',
      image_url: card.image_url || '',
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
    const data = {
      name: form.name,
      description: form.description,
      price: parseFloat(form.price),
      stock: parseInt(form.stock),
      rarity: form.rarity,
      category_id: form.category_id ? parseInt(form.category_id) : null,
      image_url: form.image_url || null,
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
            <Plus className="h-4 w-4 mr-1" />
            新規追加
          </Button>
        </div>

        {/* Form */}
        {showForm && (
          <div className="bg-gray-900 rounded-xl border border-white/10 p-6 mb-6">
            <h2 className="text-white font-semibold mb-4">
              {editingId ? 'カードを編集' : '新規カード作成'}
            </h2>
            <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label className="text-gray-300">カード名 *</Label>
                <Input value={form.name} onChange={e => setForm({...form, name: e.target.value})} required className="bg-gray-800 border-gray-700 text-white" />
              </div>
              <div className="space-y-1">
                <Label className="text-gray-300">レアリティ *</Label>
                <select value={form.rarity} onChange={e => setForm({...form, rarity: e.target.value})} className="w-full h-10 rounded-md border border-gray-700 bg-gray-800 px-3 text-white text-sm">
                  {['N', 'R', 'SR', 'SSR', 'UR'].map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div className="space-y-1">
                <Label className="text-gray-300">価格 *</Label>
                <Input type="number" value={form.price} onChange={e => setForm({...form, price: e.target.value})} required min="0" className="bg-gray-800 border-gray-700 text-white" />
              </div>
              <div className="space-y-1">
                <Label className="text-gray-300">在庫数 *</Label>
                <Input type="number" value={form.stock} onChange={e => setForm({...form, stock: e.target.value})} required min="0" className="bg-gray-800 border-gray-700 text-white" />
              </div>
              <div className="space-y-1">
                <Label className="text-gray-300">カテゴリー</Label>
                <select value={form.category_id} onChange={e => setForm({...form, category_id: e.target.value})} className="w-full h-10 rounded-md border border-gray-700 bg-gray-800 px-3 text-white text-sm">
                  <option value="">-- 選択 --</option>
                  {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
              <div className="space-y-1">
                <Label className="text-gray-300">画像URL</Label>
                <Input value={form.image_url} onChange={e => setForm({...form, image_url: e.target.value})} className="bg-gray-800 border-gray-700 text-white" />
              </div>
              <div className="sm:col-span-2 space-y-1">
                <Label className="text-gray-300">説明</Label>
                <textarea value={form.description} onChange={e => setForm({...form, description: e.target.value})} rows={2} className="w-full rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white resize-none" />
              </div>
              <div className="sm:col-span-2 flex gap-3">
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

        {/* Table */}
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
                    <th className="text-right text-gray-400 font-medium px-4 py-3">価格</th>
                    <th className="text-right text-gray-400 font-medium px-4 py-3">在庫</th>
                    <th className="text-right text-gray-400 font-medium px-4 py-3">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {cards.map((card) => (
                    <tr key={card.id} className="border-b border-white/5 hover:bg-white/5">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="relative w-8 h-10 rounded overflow-hidden bg-gray-800 flex-shrink-0">
                            {card.image_url ? (
                              <Image src={card.image_url} alt={card.name} fill className="object-cover" />
                            ) : (
                              <div className="flex items-center justify-center h-full text-sm">🃏</div>
                            )}
                          </div>
                          <span className="text-white">{card.name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-400">{card.rarity}</td>
                      <td className="px-4 py-3 text-right text-yellow-400">¥{card.price.toLocaleString()}</td>
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
