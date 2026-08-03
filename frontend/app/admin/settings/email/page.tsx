'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2, Mail } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminEmailApi } from '@/lib/api'
import { toast } from '@/lib/use-toast'

const CATEGORIES = [
  { id: 'member', label: '会員' },
  { id: 'order', label: '購入' },
  { id: 'buyback', label: '買取' },
  { id: 'point', label: 'ポイント' },
  { id: 'ops', label: '運営' },
]

type TemplateItem = {
  id: number
  template_key: string
  category: string
  name: string
  subject: string
  is_active: boolean
}

export default function AdminEmailPage() {
  const { isReady } = useAdminGuard()
  const [category, setCategory] = useState('member')
  const [templates, setTemplates] = useState<TemplateItem[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await adminEmailApi.listTemplates(category)
      setTemplates(res.data)
    } catch {
      toast({ title: 'テンプレート一覧の取得に失敗しました', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [category])

  useEffect(() => {
    if (isReady) void load()
  }, [isReady, load])

  if (!isReady) return null

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link href="/admin" className="text-gray-500 hover:text-gray-900">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Mail className="h-6 w-6" /> メールテンプレート管理
          </h1>
        </div>
        <div className="flex gap-3 text-sm">
          <Link href="/admin/settings/email/brand" className="text-cyan-600 hover:underline">
            ブランド設定
          </Link>
          <Link href="/admin/settings/email/logs" className="text-yellow-600 hover:underline">
            送信履歴
          </Link>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-6">
        {CATEGORIES.map((c) => (
          <button
            key={c.id}
            type="button"
            onClick={() => setCategory(c.id)}
            className={`px-3 py-1.5 rounded-full text-sm border ${
              category === c.id
                ? 'bg-yellow-400 border-yellow-400 text-gray-950 font-medium'
                : 'bg-white border-gray-200 text-gray-600'
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      ) : (
        <div className="space-y-2">
          {templates.map((t) => (
            <Link
              key={t.template_key}
              href={`/admin/settings/email/${encodeURIComponent(t.template_key)}`}
              className="block rounded-lg border border-gray-200 bg-white p-4 hover:border-yellow-400/50 transition-colors"
            >
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="font-medium text-gray-900">{t.name}</p>
                  <p className="text-xs text-gray-500">{t.template_key}</p>
                  <p className="text-sm text-gray-600 mt-1 truncate">{t.subject}</p>
                </div>
                <span
                  className={`text-xs px-2 py-1 rounded ${
                    t.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                  }`}
                >
                  {t.is_active ? '有効' : '無効'}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
