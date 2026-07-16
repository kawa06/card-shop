'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, Pencil, Trash2, ArrowLeft, Save, X, Bell } from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { announcementsApi } from '@/lib/api'
import { Announcement } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'
import Link from 'next/link'

export default function AdminAnnouncementsPage() {
  const router = useRouter()
  const { isAuthenticated, user, isLoading: isAuthLoading } = useAuthStore()
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const [form, setForm] = useState({
    title: '',
    content: '',
    is_active: true,
  })

  useEffect(() => {
    if (!isMounted || isAuthLoading) return

    if (!isAuthenticated) { router.push('/login'); return }
    if (user && !user.is_admin) { router.push('/'); return }
    fetchAnnouncements()
  }, [isMounted, isAuthLoading, isAuthenticated, user, router])

  const fetchAnnouncements = async () => {
    setIsLoading(true)
    try {
      const res = await announcementsApi.getAll()
      setAnnouncements(res.data || [])
    } finally {
      setIsLoading(false)
    }
  }

  const handleEdit = (ann: Announcement) => {
    setEditingId(ann.id)
    setForm({
      title: ann.title,
      content: ann.content,
      is_active: ann.is_active,
    })
    setShowForm(true)
  }

  const handleDelete = async (id: number) => {
    if (!confirm('このお知らせを削除しますか？')) return
    try {
      // 実際には adminApi に deleteAnnouncement があるか確認が必要
      // なければ announcementsApi に追加検討
      await announcementsApi.delete(id)
      toast({ title: '削除しました' })
      fetchAnnouncements()
    } catch {
      toast({ title: 'エラー', description: '削除に失敗しました', variant: 'destructive' })
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      if (editingId) {
        await announcementsApi.update(editingId, form)
        toast({ title: '更新しました' })
      } else {
        await announcementsApi.create(form)
        toast({ title: '作成しました' })
      }
      setShowForm(false)
      setEditingId(null)
      setForm({ title: '', content: '', is_active: true })
      fetchAnnouncements()
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
          <Bell className="h-6 w-6 text-purple-400" />
          <h1 className="text-2xl font-bold text-gray-900 flex-1">お知らせ管理</h1>
          <Button
            onClick={() => { setShowForm(true); setEditingId(null); setForm({ title: '', content: '', is_active: true }) }}
            className="bg-purple-600 text-white hover:bg-purple-500 font-bold"
          >
            <Plus className="h-4 w-4 mr-1" />
            新規追加
          </Button>
        </div>

        {showForm && (
          <div className="bg-gray-50 rounded-xl border border-gray-200 p-6 mb-8">
            <h2 className="text-gray-900 font-semibold mb-4">
              {editingId ? 'お知らせを編集' : '新規お知らせ作成'}
            </h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1">
                <Label className="text-gray-600">タイトル</Label>
                <Input
                  value={form.title}
                  onChange={e => setForm({...form, title: e.target.value})}
                  required
                  className="bg-white border-gray-300 text-gray-900"
                  placeholder="重要なお知らせ"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-gray-600">内容</Label>
                <textarea
                  value={form.content}
                  onChange={e => setForm({...form, content: e.target.value})}
                  required
                  rows={3}
                  className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 resize-none focus:outline-none focus:ring-1 focus:ring-purple-500"
                  placeholder="お知らせの詳細内容を入力してください"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_active"
                  checked={form.is_active}
                  onChange={e => setForm({...form, is_active: e.target.checked})}
                  className="w-4 h-4 rounded border-gray-300 bg-white text-purple-600 focus:ring-purple-500"
                />
                <Label htmlFor="is_active" className="text-gray-600 cursor-pointer">
                  公開する
                </Label>
              </div>
              <div className="flex gap-3 pt-2">
                <Button type="submit" disabled={saving} className="bg-purple-600 text-white hover:bg-purple-500 font-bold">
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
          ) : announcements.length === 0 ? (
            <div className="p-8 text-center text-gray-500">お知らせはありません</div>
          ) : (
            <div className="divide-y divide-gray-100">
              {announcements.map((ann) => (
                <div key={ann.id} className="p-4 flex items-center justify-between hover:bg-gray-100 transition-colors">
                  <div className="flex-1 min-w-0 pr-4">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-gray-900 font-medium truncate">{ann.title}</h3>
                      {!ann.is_active && (
                        <span className="text-[10px] bg-white text-gray-500 px-1.5 py-0.5 rounded border border-gray-100">
                          非公開
                        </span>
                      )}
                    </div>
                    <p className="text-gray-400 text-sm truncate">{ann.content}</p>
                    <p className="text-[10px] text-gray-600 mt-1">
                      {new Date(ann.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="ghost" size="icon" onClick={() => handleEdit(ann)} className="h-8 w-8 text-blue-400 hover:text-blue-300">
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => handleDelete(ann.id)} className="h-8 w-8 text-red-400 hover:text-red-300">
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