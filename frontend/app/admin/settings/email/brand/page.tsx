'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2, Palette, Save } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminEmailApi } from '@/lib/api'
import { toast } from '@/lib/use-toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

type BrandSettings = {
  logo_url?: string | null
  sender_name?: string | null
  brand_color?: string | null
  footer_text?: string | null
  sns_links_json?: string | null
  terms_url?: string | null
  contact_url?: string | null
  privacy_url?: string | null
  company_name?: string | null
  company_address?: string | null
  contact_email?: string | null
  contact_phone?: string | null
}

export default function AdminEmailBrandPage() {
  const { isReady } = useAdminGuard()
  const [brand, setBrand] = useState<BrandSettings>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await adminEmailApi.getBrand()
      setBrand(res.data)
    } catch {
      toast({ title: 'ブランド設定の取得に失敗しました', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isReady) void load()
  }, [isReady, load])

  const handleSave = async () => {
    setSaving(true)
    try {
      const res = await adminEmailApi.updateBrand(brand)
      setBrand(res.data)
      toast({ title: 'ブランド設定を保存しました' })
    } catch {
      toast({ title: '保存に失敗しました', variant: 'destructive' })
    } finally {
      setSaving(false)
    }
  }

  if (!isReady || loading) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl">
      <Link href="/admin/settings/email" className="inline-flex items-center gap-2 text-gray-500 mb-4">
        <ArrowLeft className="h-4 w-4" /> メールテンプレート管理
      </Link>
      <h1 className="text-2xl font-bold flex items-center gap-2 mb-6">
        <Palette className="h-6 w-6 text-cyan-600" /> ブランド・共通設定
      </h1>
      <p className="text-sm text-gray-500 mb-6">
        差出人名・フッター・SNSリンク・会社情報など、全メールに共通で反映される設定です。保存ボタンを押した時のみ反映されます。
      </p>

      <div className="space-y-5 bg-white border rounded-xl p-6">
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <Label>差出人名</Label>
            <Input
              value={brand.sender_name || ''}
              onChange={(e) => setBrand({ ...brand, sender_name: e.target.value })}
              placeholder="KRX TCG"
            />
          </div>
          <div>
            <Label>ブランドカラー</Label>
            <Input
              type="color"
              value={brand.brand_color || '#fbbf24'}
              onChange={(e) => setBrand({ ...brand, brand_color: e.target.value })}
              className="h-10"
            />
          </div>
        </div>

        <div>
          <Label>ロゴURL</Label>
          <Input
            value={brand.logo_url || ''}
            onChange={(e) => setBrand({ ...brand, logo_url: e.target.value })}
            placeholder="https://..."
          />
        </div>

        <div>
          <Label>フッターテキスト</Label>
          <textarea
            className="w-full min-h-[80px] rounded-md border border-gray-200 p-3 text-sm"
            value={brand.footer_text || ''}
            onChange={(e) => setBrand({ ...brand, footer_text: e.target.value })}
          />
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          <div>
            <Label>利用規約URL</Label>
            <Input value={brand.terms_url || ''} onChange={(e) => setBrand({ ...brand, terms_url: e.target.value })} />
          </div>
          <div>
            <Label>お問い合わせURL</Label>
            <Input value={brand.contact_url || ''} onChange={(e) => setBrand({ ...brand, contact_url: e.target.value })} />
          </div>
          <div>
            <Label>プライバシーURL</Label>
            <Input value={brand.privacy_url || ''} onChange={(e) => setBrand({ ...brand, privacy_url: e.target.value })} />
          </div>
        </div>

        <div>
          <Label>SNSリンク（JSON）</Label>
          <textarea
            className="w-full min-h-[100px] rounded-md border border-gray-200 p-3 font-mono text-xs"
            value={brand.sns_links_json || '[]'}
            onChange={(e) => setBrand({ ...brand, sns_links_json: e.target.value })}
            placeholder='[{"label":"Instagram","url":"https://..."}]'
          />
        </div>

        <div className="border-t pt-4">
          <h2 className="font-semibold mb-3">会社情報</h2>
          <div className="space-y-3">
            <div>
              <Label>会社名</Label>
              <Input value={brand.company_name || ''} onChange={(e) => setBrand({ ...brand, company_name: e.target.value })} />
            </div>
            <div>
              <Label>住所</Label>
              <textarea
                className="w-full min-h-[60px] rounded-md border border-gray-200 p-3 text-sm"
                value={brand.company_address || ''}
                onChange={(e) => setBrand({ ...brand, company_address: e.target.value })}
              />
            </div>
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <Label>問い合わせメール</Label>
                <Input value={brand.contact_email || ''} onChange={(e) => setBrand({ ...brand, contact_email: e.target.value })} />
              </div>
              <div>
                <Label>問い合わせ電話</Label>
                <Input value={brand.contact_phone || ''} onChange={(e) => setBrand({ ...brand, contact_phone: e.target.value })} />
              </div>
            </div>
          </div>
        </div>

        <Button onClick={handleSave} disabled={saving} className="w-full md:w-auto">
          <Save className="h-4 w-4 mr-1" />
          {saving ? '保存中…' : '保存'}
        </Button>
      </div>
    </div>
  )
}
