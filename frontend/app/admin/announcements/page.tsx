'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Plus, Pencil, Trash2, ArrowLeft, CheckCircle, XCircle } from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { announcementsApi, adminApi } from '@/lib/api'
import { Announcement } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

export default function AdminAnnouncementsPage() {
  const router = useRouter()
  const { isAuthenticated, user } = useAuthStore()
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [isActive, setIsActive] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!isAuthenticated) { router.push('/login'); return }
    if (user && !user.is_admin) { router.push('/'); return }
    fetchAll()
  }, [isAuthenticated, user, router])

  const fetchAll = async () => {
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
    setTitle(ann.title)
    setContent(ann.content)
    setIsActive(ann.is_active)
    setShowForm(true)
  }

  const handleDelete = async (id: number, annTitle: string) => {
    if (!confirm(`「${annTitle}」を削除しますか？`)) return
    try {
      await adminApi.deleteAnnouncement(id)
      toast({ title: '削除しました' })
      fetchAll()
    } catch {
      toast({ title: 'エラー', description: '削除に失敗しました', variant: 'destructive' })
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      if (editingId) {
        await adminApi.updateAnnouncement(editingId, { title, content, is_active: isActive })
        toast({ title: '更新しました' })
      } else {
        await adminApi.createAnnouncement({ title, content, is_active: isActive })
        toast({ title: '作成しました' })
      }
      setShowForm(false)
      setEditingId(null)
      fetchAll()
    } catch {
      toast({ title: 'エラー', description: '保存に失敗しました', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="container py-8 max-w-3xl">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/admin">
            <Button variant="ghost" size="icon" className="text-gray-400 hover:text-white">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <h1 className="text-2xl font-bold text-white flex-1">お知らせ管理</h1>
          <Button onClick={() => { setShowForm(true); setEditingId(null); setTitle(''); setContent(''); setIsActive(true) }} className="bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold">
            <Plus className="h-4 w-4 mr-1" />
            新規追加
          </Button>
        </div>

        {showForm && (
          <div className="bg-gray-900 rounded-xl border border-white/10 p-6 mb-6">
            <h2 className="text-white font-semibold mb-4">{editingId ? 'お知らせを編集' : '新規お知らせ作成'}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1">
                <Label className="text-gray-300">タイトル *</Label>
                <Input value={title} onChange={e => setTitle(e.target.value)} required className="bg-gray-800 border-gray-700 text-white" />
              </div>
              <div className="space-y-1">
                <Label className="text-gray-300">内容 *</Label>
                <textarea value={content} onChange={e => setContent(e.target.value)} required rows={3} className="w-full rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white resize-none" />
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={isActive} onChange={e => setIsActive(e.target.checked)} className="accent-yellow-400" />
                <span className="text-gray-300 text-sm">公開する</span>
              </label>
              <div className="flex gap-3">
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

        <div className="bg-gray-900 rounded-xl border border-white/10 overflow-hidden">
          {isLoading ? (
            <div className="p-8 text-center text-gray-400 animate-pulse">読み込み中...</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b border-white/10">
                <tr>
                  <th className="text-left text-gray-400 font-medium px-4 py-3">タイトル</th>
                  <th className="text-left text-gray-400 font-medium px-4 py-3">状態</th>
                  <th className="text-right text-gray-400 font-medium px-4 py-3">操作</th>
                </tr>
              </thead>
              <tbody>
                {announcements.map((ann) => (
                  <tr key={ann.id} className="border-b border-white/5 hover:bg-white/5">
                    <td className="px-4 py-3">
                      <p className="text-white">{ann.title}</p>
                      <p className="text-gray-500 text-xs truncate max-w-xs">{ann.content}</p>
                    </td>
                    <td className="px-4 py-3">
                      {ann.is_active ? (
                        <span className="flex items-center gap-1 text-green-400 text-xs"><CheckCircle className="h-3 w-3" />公開中</span>
                      ) : (
                        <span className="flex items-center gap-1 text-gray-500 text-xs"><XCircle className="h-3 w-3" />非公開</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-2">
                        <Button variant="ghost" size="icon" onClick={() => handleEdit(ann)} className="h-8 w-8 text-blue-400 hover:text-blue-300">
                          <Pencil className="h-3 w-3" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => handleDelete(ann.id, ann.title)} className="h-8 w-8 text-red-400 hover:text-red-300">
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
