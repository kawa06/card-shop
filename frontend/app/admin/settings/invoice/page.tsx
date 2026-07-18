'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2, Save } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminApi } from '@/lib/api'
import { invalidateInvoiceConfigCache } from '@/hooks/useInvoiceConfig'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

export default function AdminInvoiceSettingsPage() {
  const { isReady } = useAdminGuard()
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isMounted, setIsMounted] = useState(false)
  const [invoiceEnabled, setInvoiceEnabled] = useState(false)
  const [registrationNumber, setRegistrationNumber] = useState('')
  const [issuerName, setIssuerName] = useState('')
  const [defaultTaxRate, setDefaultTaxRate] = useState('10')
  const [qualifiedEnabled, setQualifiedEnabled] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const loadSettings = useCallback(async () => {
    setIsLoading(true)
    try {
      const res = await adminApi.getInvoiceSettings()
      const d = res.data
      setInvoiceEnabled(Boolean(d.invoice_enabled))
      setRegistrationNumber(d.invoice_registration_number || '')
      setIssuerName(d.invoice_issuer_name || '')
      setDefaultTaxRate(String(d.default_tax_rate || 10))
      setQualifiedEnabled(Boolean(d.qualified_invoice_enabled))
    } catch {
      toast({ title: '設定の取得に失敗しました', variant: 'destructive' })
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void loadSettings()
  }, [isMounted, isReady, loadSettings])

  const handleSave = async () => {
    setIsSaving(true)
    try {
      const rate = parseInt(defaultTaxRate, 10)
      const res = await adminApi.updateInvoiceSettings({
        invoice_enabled: invoiceEnabled,
        invoice_registration_number: registrationNumber.trim() || null,
        invoice_issuer_name: issuerName.trim() || null,
        default_tax_rate: rate,
      })
      setQualifiedEnabled(Boolean(res.data.qualified_invoice_enabled))
      setRegistrationNumber(res.data.invoice_registration_number || '')
      setIssuerName(res.data.invoice_issuer_name || '')
      invalidateInvoiceConfigCache()
      toast({ title: 'インボイス設定を保存しました' })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast({
        title: '保存に失敗しました',
        description: typeof detail === 'string' ? detail : undefined,
        variant: 'destructive',
      })
    } finally {
      setIsSaving(false)
    }
  }

  if (!isMounted || !isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-xl">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/admin">
            <Button variant="ghost" size="icon" className="text-gray-400 hover:text-gray-900">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">インボイス設定</h1>
        </div>

        {isLoading ? (
          <div className="flex items-center gap-2 text-gray-400 py-12 justify-center">
            <Loader2 className="h-5 w-5 animate-spin" />
            読み込み中...
          </div>
        ) : (
          <div className="space-y-6 bg-gray-50 rounded-xl border border-gray-200 p-6">
            <p className="text-sm text-gray-600">
              登録番号が未設定、または条件を満たさない場合、購入者向け書類には適格請求書の項目は表示されません。
            </p>

            <div className="flex items-center gap-3">
              <input
                id="invoice-enabled"
                type="checkbox"
                checked={invoiceEnabled}
                onChange={(e) => setInvoiceEnabled(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300"
              />
              <Label htmlFor="invoice-enabled" className="text-sm font-medium cursor-pointer">
                適格請求書機能を有効にする
              </Label>
            </div>

            <div className="space-y-2">
              <Label htmlFor="reg-number">登録番号（T + 13桁）</Label>
              <Input
                id="reg-number"
                value={registrationNumber}
                onChange={(e) => setRegistrationNumber(e.target.value)}
                placeholder="T1234567890123"
                className="font-mono bg-white"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="issuer-name">適格請求書発行事業者名</Label>
              <Input
                id="issuer-name"
                value={issuerName}
                onChange={(e) => setIssuerName(e.target.value)}
                placeholder="川村 海斗"
                className="bg-white"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="tax-rate">標準税率（%）</Label>
              <select
                id="tax-rate"
                value={defaultTaxRate}
                onChange={(e) => setDefaultTaxRate(e.target.value)}
                className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm"
              >
                <option value="10">10%</option>
                <option value="8">8%</option>
              </select>
            </div>

            <div className="rounded-lg border border-gray-200 bg-white p-4 text-sm">
              <p className="text-gray-500 mb-1">現在の状態</p>
              <p className="font-medium text-gray-900">
                {qualifiedEnabled
                  ? '適格請求書として発行可能'
                  : '通常の購入明細書・領収書・請求書として発行'}
              </p>
            </div>

            <Button onClick={handleSave} disabled={isSaving} className="gap-2">
              {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              保存
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
