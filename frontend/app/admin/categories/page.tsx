'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, Pencil, Trash2, ArrowLeft, Tag } from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { categoriesApi, adminApi } from '@/lib/api'
import { Category } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'
import Link from 'next/link'

export default function AdminCategoriesPage() {
  const router = useRouter()
  const { isAuthenticated, user } = useAuthStore()
  const [categories, setCategories] = useState<Category[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)

  const [form, setForm] = useState({
    name: '',
    description: '',
  })

  useEffect(() => {
    if (!isAuthenticated) { router.push('/login'); return }
    if (user && !user.is_admin) { router.push('/'); return }
    fetchCategories()
  }, [isAuthenticated, user, router])

  const fetchCategories = async () => {
    setIsLoading(true)
    try {
      const res = await categoriesApi.getAll()
      setCategories(res.data || [])
    } finally {
      setIsLoading(false)
    }
  }

  const handleEdit = (cat: Category) => {
    setEditingId(cat.id)
    setForm({
      name: cat.name,
      description: cat.description || '',
    })
    setShowForm(true)
  }

  const handleDelete = async (id: number) => {
    if (!confirm('このカテゴリーを削除しますか？紐付いているカードがある場合はエラーになる可能性があります。')) return
    try {
      await adminApi.deleteCategory(id)
      toast({ title: '削除しました' })
      fetchCategories()
    } catch {
      toast({ title: 'エラー', description: '削除に失敗しました', variant: 'destructive' })
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      if (editingId) {
        await adminApi.updateCategory(editingId, form)
        toast({ title: '更新しました' })
      } else {
        await adminApi.createCategory(form)
        toast({ title: '作成しました' })
      }
      setShowForm(false)
      setEditingId(null)
      setForm({ name: '', description: '' })
      fetchCategories()
    } catch {
      toast({ title: 'エラー', description: '保存に失敗しました', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="container py-8 max-w-4xl">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/admin">
            <Button variant="ghost" size="icon" className="text-gray-400 hover:text-white">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <Tag className="h-6 w-6 text-blue-400" />
          <h1 className="text-2xl font-bold text-white flex-1">カテゴリー管理</h1>
          <Button
            onClick={() => { setShowForm(true); setEditingId(null); setForm({ name: '', description: '' }) }}
            className="bg-blue-600 text-white hover:bg-blue-500 font-bold"
          >
            <Plus className="h-4 w-4 mr-1" />
            新規追加
          </Button>
        </div>

        {showForm && (
          <div className="bg-gray-900 rounded-xl border border-white/10 p-6 mb-8">
            <h2 className="text-white font-semibold mb-4">
              {editingId ? 'カテゴリーを編集' : '新規カテゴリー作成'}
            </h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1">
                <Label className="text-gray-300">カテゴリー名</Label>
                <Input
                  value={form.name}
                  onChange={e => setForm({...form, name: e.target.value})}
                  required
                  className="bg-gray-800 border-gray-700 text-white"
                  placeholder="例: ポケモンカード"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-gray-300">説明</Label>
                <Input
                  value={form.description}
                  onChange={e => setForm({...form, description: e.target.value})}
                  className="bg-gray-800 border-gray-700 text-white"
                  placeholder="カテゴリーの説明（任意）"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <Button type="submit" disabled={saving} className="bg-blue-600 text-white hover:bg-blue-500 font-bold">
                  {saving ? '保存中...' : editingId ? '更新' : '作成'}
                </Button>
                <Button type="button" variant="ghost" onClick={() => { setShowForm(false); setEditingId(null) }} className="text-gray-400">
                  キャンセル
                </Button>
              </div>
            </form>
          </div>
        )}

        <div className="bg-gray-900 rounded-xl border border-white/10 overflow-hidden">
          {isLoading ? (
            <div className="p-8 text-center text-gray-400 animate-pulse">読み込み中...</div>
          ) : categories.length === 0 ? (
            <div className="p-8 text-center text-gray-500">カテゴリーはありません</div>
          ) : (
            <div className="divide-y divide-white/5">
              {categories.map((cat) => (
                <div key={cat.id} className="p-4 flex items-center justify-between hover:bg-white/5 transition-colors">
                  <div className="flex-1 min-w-0 pr-4">
                    <h3 className="text-white font-medium truncate">{cat.name}</h3>
                    {cat.description && (
                      <p className="text-gray-400 text-sm truncate">{cat.description}</p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Button variant="ghost" size="icon" onClick={() => handleEdit(cat)} className="h-8 w-8 text-blue-400 hover:text-blue-300">
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => handleDelete(cat.id)} className="h-8 w-8 text-red-400 hover:text-red-300">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}