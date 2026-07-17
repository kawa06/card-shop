'use client'

import { useState, useEffect } from 'react'
import { Plus, Pencil, Trash2, ArrowLeft, Package } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { packsApi, adminApi } from '@/lib/api'
import { Pack } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'
import Link from 'next/link'

function slugFromName(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
  return slug || `pack-${Date.now()}`
}

export default function AdminPacksPage() {
  const { isReady } = useAdminGuard()
  const [packs, setPacks] = useState<Pack[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [isMounted, setIsMounted] = useState(false)
  const [form, setForm] = useState({ name: '', sort_order: '0' })

  useEffect(() => {
    setIsMounted(true)
  }, [])

  useEffect(() => {
    if (!isMounted || !isReady) return
    fetchPacks()
  }, [isMounted, isReady])

  const fetchPacks = async () => {
    setIsLoading(true)
    try {
      const res = await packsApi.getAll()
      setPacks(res.data || [])
    } finally {
      setIsLoading(false)
    }
  }

  const handleEdit = (pack: Pack) => {
    setEditingId(pack.id)
    setForm({ name: pack.name, sort_order: String(pack.sort_order ?? 0) })
    setShowForm(true)
  }

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`「${name}」を削除しますか？\n紐付いているカードは削除されず、パック未設定になります。`)) return
    try {
      await adminApi.deletePack(id)
      toast({ title: '削除しました' })
      fetchPacks()
    } catch {
      toast({ title: 'エラー', description: '削除に失敗しました', variant: 'destructive' })
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload = {
        name: form.name.trim(),
        slug: slugFromName(form.name.trim()),
        sort_order: parseInt(form.sort_order, 10) || 0,
      }
      if (editingId) {
        await adminApi.updatePack(editingId, payload)
        toast({ title: '更新しました' })
      } else {
        await adminApi.createPack(payload)
        toast({ title: '作成しました' })
      }
      setShowForm(false)
      setEditingId(null)
      setForm({ name: '', sort_order: '0' })
      fetchPacks()
    } catch {
      toast({ title: 'エラー', description: '保存に失敗しました', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-4xl">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/admin">
            <Button variant="ghost" size="icon" className="text-gray-400 hover:text-gray-900">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <Package className="h-6 w-6 text-sky-400" />
          <h1 className="text-2xl font-bold text-gray-900 flex-1">パック管理</h1>
          <Button
            onClick={() => { setShowForm(true); setEditingId(null); setForm({ name: '', sort_order: '0' }) }}
            className="bg-sky-600 text-white hover:bg-sky-500 font-bold"
          >
            <Plus className="h-4 w-4 mr-1" />
            新規追加
          </Button>
        </div>

        {showForm && (
          <div className="bg-gray-50 rounded-xl border border-gray-200 p-6 mb-8">
            <h2 className="text-gray-900 font-semibold mb-4">
              {editingId ? 'パックを編集' : '新規パック作成'}
            </h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1">
                <Label className="text-gray-600">パック名 *</Label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                  className="bg-white border-gray-300 text-gray-900"
                  placeholder="例: 拡張パック「メガシンフォニア」"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-gray-600">表示順</Label>
                <Input
                  type="number"
                  value={form.sort_order}
                  onChange={(e) => setForm({ ...form, sort_order: e.target.value })}
                  className="bg-white border-gray-300 text-gray-900 w-32"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <Button type="submit" disabled={saving} className="bg-sky-600 text-white hover:bg-sky-500 font-bold">
                  {saving ? '保存中...' : editingId ? '更新' : '作成'}
                </Button>
                <Button type="button" variant="ghost" onClick={() => { setShowForm(false); setEditingId(null) }} className="text-gray-400">
                  キャンセル
                </Button>
              </div>
            </form>
          </div>
        )}

        <div className="bg-gray-50 rounded-xl border border-gray-200 overflow-hidden">
          {isLoading ? (
            <div className="p-8 text-center text-gray-400 animate-pulse">読み込み中...</div>
          ) : packs.length === 0 ? (
            <div className="p-8 text-center text-gray-500">パックはまだ登録されていません</div>
          ) : (
            <div className="divide-y divide-gray-100">
              {packs.map((pack) => (
                <div key={pack.id} className="p-4 flex items-center justify-between hover:bg-gray-100 transition-colors">
                  <div className="flex-1 min-w-0 pr-4">
                    <h3 className="text-gray-900 font-medium truncate">{pack.name}</h3>
                    <p className="text-gray-400 text-xs">表示順: {pack.sort_order}</p>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="ghost" size="icon" onClick={() => handleEdit(pack)} className="h-8 w-8 text-sky-400 hover:text-sky-300">
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => handleDelete(pack.id, pack.name)} className="h-8 w-8 text-red-400 hover:text-red-300">
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
