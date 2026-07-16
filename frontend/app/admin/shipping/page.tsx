'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, RefreshCw, ExternalLink, Shield, Globe, Truck, Edit2, Save, X } from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { shippingApi } from '@/lib/api'
import { ShippingRate } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { toast } from '@/lib/use-toast'
import { usePrice } from '@/lib/format'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"

export default function AdminShippingPage() {
  const router = useRouter()
  const { isAuthenticated, user, isLoading: isAuthLoading } = useAuthStore()
  const { lang } = useLangStore()
  const { formatPrice } = usePrice()
  const [rates, setRates] = useState<ShippingRate[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isMounted, setIsMounted] = useState(false)

  // Edit State
  const [editingRate, setEditingRate] = useState<ShippingRate | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const fetchRates = async () => {
    setIsLoading(true)
    try {
      const res = await shippingApi.getRates()
      setRates(res.data)
    } catch (err) {
      toast({ title: 'Error', description: 'Failed to fetch shipping rates', variant: 'destructive' })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!isMounted || isAuthLoading) return
    if (!isAuthenticated || (user && !user.is_admin)) {
      router.push('/')
      return
    }
    fetchRates()
  }, [isMounted, isAuthLoading, isAuthenticated, user, router])

  const handleRefresh = async () => {
    setIsRefreshing(true)
    try {
      await shippingApi.refreshRates()
      toast({ title: 'Success', description: 'Shipping rates updated from official sources' })
      await fetchRates()
    } catch (err) {
      toast({ title: 'Error', description: 'Failed to refresh rates', variant: 'destructive' })
    } finally {
      setIsRefreshing(false)
    }
  }

  const handleEdit = (rate: ShippingRate) => {
    setEditingRate({ ...rate })
  }

  const handleSave = async () => {
    if (!editingRate) return
    setIsSaving(true)
    try {
      await shippingApi.updateRate(editingRate.method_code, editingRate)
      toast({ title: 'Success', description: 'Shipping rate updated successfully' })
      setEditingRate(null)
      fetchRates()
    } catch (err) {
      toast({ title: 'Error', description: 'Failed to update shipping rate', variant: 'destructive' })
    } finally {
      setIsSaving(false)
    }
  }

  if (!isMounted || !isAuthenticated || (user && !user.is_admin)) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-5xl">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push('/admin')}
              className="p-2 rounded-full hover:bg-gray-100 text-gray-400 hover:text-gray-900 transition-colors"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Truck className="h-6 w-6 text-orange-400" />
              {t('送料管理', lang)}
            </h1>
          </div>
          <Button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="bg-orange-500 hover:bg-orange-600 text-white font-bold flex items-center gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            {lang === 'ja' ? '最新料金を取得' : 'Refresh Rates'}
          </Button>
        </div>

        {isLoading ? (
          <div className="grid gap-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-32 bg-gray-50 rounded-xl border border-gray-100 animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="space-y-8">
            {Object.entries(
              rates.reduce((acc, rate) => {
                const carrier = rate.carrier || 'other'
                if (!acc[carrier]) acc[carrier] = []
                acc[carrier].push(rate)
                return acc
              }, {} as Record<string, ShippingRate[]>)
            ).map(([carrier, carrierRates]) => (
              <div key={carrier} className="space-y-4">
                <h2 className="text-xs uppercase tracking-[0.2em] text-gray-500 font-black flex items-center gap-2 ml-2">
                  <div className="h-px w-8 bg-gray-200" />
                  {carrier === 'yamato' ? 'Yamato Transport' : carrier === 'japan_post' ? 'Japan Post' : 'Other Carriers'}
                </h2>
                <div className="grid gap-4">
                  {carrierRates.map((rate) => (
                    <div key={rate.method_code} className="bg-gray-50 rounded-xl border border-gray-200 p-6 hover:border-gray-300 transition-all group">
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-1">
                            <h3 className="text-lg font-bold text-gray-900 group-hover:text-orange-400 transition-colors">
                              {lang === 'ja' ? rate.name_ja : rate.name_en}
                            </h3>
                            <span className="text-[10px] bg-white text-gray-400 px-2 py-0.5 rounded border border-gray-100">
                              {rate.method_code}
                            </span>
                            {rate.is_recommended && (
                              <Badge className="bg-yellow-400 text-gray-950 text-[9px] h-4 px-1 font-bold">
                                RECOMMENDED
                              </Badge>
                            )}
                          </div>
                          <div className="flex flex-wrap gap-2 mb-3">
                            {rate.is_international_available && (
                              <span className="text-[10px] bg-purple-500/10 text-purple-400 px-2 py-0.5 rounded border border-purple-500/20 flex items-center gap-1">
                                <Globe className="h-3 w-3" /> International
                              </span>
                            )}
                            {rate.has_tracking && (
                              <span className="text-[10px] bg-green-500/10 text-green-400 px-2 py-0.5 rounded border border-green-500/20 flex items-center gap-1">
                                <Truck className="h-3 w-3" /> {t('追跡有', lang)}
                              </span>
                            )}
                            {rate.has_insurance ? (
                              <span className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded border border-blue-500/20 flex items-center gap-1">
                                <Shield className="h-3 w-3" /> {t('補償有', lang)} {rate.insurance_max_amount ? `(Max ${formatPrice(rate.insurance_max_amount)})` : ''}
                              </span>
                            ) : (
                              <span className="text-[10px] bg-red-500/10 text-red-400 px-2 py-0.5 rounded border border-red-500/20 flex items-center gap-1">
                                <Shield className="h-3 w-3" /> {t('補償無', lang)}
                              </span>
                            )}
                            {rate.estimated_delivery_min_days && (
                              <span className="text-[10px] bg-yellow-500/10 text-yellow-400 px-2 py-0.5 rounded border border-yellow-500/20">
                                {rate.estimated_delivery_min_days}-{rate.estimated_delivery_max_days} {t('日', lang)}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-4">
                            {rate.source_url && (
                              <a
                                href={rate.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-gray-500 hover:text-orange-400 flex items-center gap-1 transition-colors"
                              >
                                <ExternalLink className="h-3 w-3" />
                                {lang === 'ja' ? '参照元ページ' : 'Source URL'}
                              </a>
                            )}
                            {rate.insurance_url && (
                              <a
                                href={rate.insurance_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-gray-500 hover:text-orange-400 flex items-center gap-1 transition-colors"
                              >
                                <ExternalLink className="h-3 w-3" />
                                {t('補償詳細', lang)}
                              </a>
                            )}
                          </div>
                        </div>
                        <div className="flex flex-row md:flex-col items-center md:items-end gap-4 md:gap-2">
                          <div className="text-right">
                            <p className="text-2xl font-bold text-orange-400">
                              {formatPrice(rate.fee_jpy)}
                            </p>
                            <p className="text-[10px] text-gray-500 mt-1">
                              {t('最終更新', lang)}: {new Date(rate.updated_at).toLocaleString(lang === 'ja' ? 'ja-JP' : 'en-US')}
                            </p>
                          </div>
                          <Button
                            onClick={() => handleEdit(rate)}
                            variant="outline"
                            size="sm"
                            className="border-gray-200 hover:bg-gray-100 text-gray-400 hover:text-gray-900"
                          >
                            <Edit2 className="h-3 w-3 mr-2" />
                            {t('編集', lang)}
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Edit Dialog */}
        <Dialog open={!!editingRate} onOpenChange={(open: boolean) => !open && setEditingRate(null)}>
          <DialogContent className="bg-gray-50 border-gray-200 text-gray-900 max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="text-xl font-bold flex items-center gap-2">
                <Edit2 className="h-5 w-5 text-orange-400" />
                {editingRate ? (lang === 'ja' ? editingRate.name_ja : editingRate.name_en) : ''}
              </DialogTitle>
            </DialogHeader>
            
            {editingRate && (
              <div className="grid gap-6 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-gray-400 text-xs uppercase tracking-wider font-black">{lang === 'ja' ? '名称 (JP)' : 'Name (JP)'}</Label>
                    <Input
                      value={editingRate.name_ja}
                      onChange={(e) => setEditingRate({ ...editingRate, name_ja: e.target.value })}
                      className="bg-white border-gray-100 text-gray-900"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-gray-400 text-xs uppercase tracking-wider font-black">{lang === 'ja' ? '名称 (EN)' : 'Name (EN)'}</Label>
                    <Input
                      value={editingRate.name_en}
                      onChange={(e) => setEditingRate({ ...editingRate, name_en: e.target.value })}
                      className="bg-white border-gray-100 text-gray-900"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-gray-400 text-xs uppercase tracking-wider font-black">{lang === 'ja' ? '基本料金 (JPY)' : 'Base Fee (JPY)'}</Label>
                    <Input
                      type="number"
                      value={editingRate.fee_jpy}
                      onChange={(e) => setEditingRate({ ...editingRate, fee_jpy: parseInt(e.target.value) })}
                      className="bg-white border-gray-100 text-gray-900"
                    />
                  </div>
                  <div className="flex items-center gap-4 mt-8">
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id="is_recommended"
                        checked={editingRate.is_recommended}
                        onCheckedChange={(checked: boolean) => setEditingRate({ ...editingRate, is_recommended: !!checked })}
                      />
                      <label htmlFor="is_recommended" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                        {t('推奨', lang)}
                      </label>
                    </div>
                  </div>
                </div>

                <div className="space-y-4 border-t border-gray-100 pt-4">
                  <h4 className="text-sm font-bold text-orange-400">{lang === 'ja' ? '配送・追跡・補償設定' : 'Shipping & Insurance Settings'}</h4>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id="is_international"
                        checked={editingRate.is_international_available}
                        onCheckedChange={(checked: boolean) => setEditingRate({ ...editingRate, is_international_available: !!checked })}
                      />
                      <label htmlFor="is_international" className="text-xs font-medium">International</label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id="has_tracking"
                        checked={editingRate.has_tracking}
                        onCheckedChange={(checked: boolean) => setEditingRate({ ...editingRate, has_tracking: !!checked })}
                      />
                      <label htmlFor="has_tracking" className="text-xs font-medium">{t('追跡', lang)}</label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id="has_insurance"
                        checked={editingRate.has_insurance}
                        onCheckedChange={(checked: boolean) => setEditingRate({ ...editingRate, has_insurance: !!checked })}
                      />
                      <label htmlFor="has_insurance" className="text-xs font-medium">{t('補償', lang)}</label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id="is_individual"
                        checked={editingRate.is_individual_available}
                        onCheckedChange={(checked: boolean) => setEditingRate({ ...editingRate, is_individual_available: !!checked })}
                      />
                      <label htmlFor="is_individual" className="text-xs font-medium">{lang === 'ja' ? '個人利用可' : 'Individual OK'}</label>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4 border-t border-gray-100 pt-4">
                  <div className="space-y-2">
                    <Label className="text-gray-400 text-xs uppercase tracking-wider font-black">{lang === 'ja' ? '補償上限 (JPY)' : 'Max Insurance (JPY)'}</Label>
                    <Input
                      type="number"
                      value={editingRate.insurance_max_amount || 0}
                      onChange={(e) => setEditingRate({ ...editingRate, insurance_max_amount: parseInt(e.target.value) })}
                      className="bg-white border-gray-100 text-gray-900"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-gray-400 text-xs uppercase tracking-wider font-black">{lang === 'ja' ? '配達日数 (最小)' : 'Min Delivery Days'}</Label>
                    <Input
                      type="number"
                      value={editingRate.estimated_delivery_min_days || 0}
                      onChange={(e) => setEditingRate({ ...editingRate, estimated_delivery_min_days: parseInt(e.target.value) })}
                      className="bg-white border-gray-100 text-gray-900"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-gray-400 text-xs uppercase tracking-wider font-black">{lang === 'ja' ? '配達日数 (最大)' : 'Max Delivery Days'}</Label>
                    <Input
                      type="number"
                      value={editingRate.estimated_delivery_max_days || 0}
                      onChange={(e) => setEditingRate({ ...editingRate, estimated_delivery_max_days: parseInt(e.target.value) })}
                      className="bg-white border-gray-100 text-gray-900"
                    />
                  </div>
                </div>

                <div className="space-y-2 border-t border-gray-100 pt-4">
                  <Label className="text-gray-400 text-xs uppercase tracking-wider font-black">{lang === 'ja' ? '補償詳細URL' : 'Insurance Info URL'}</Label>
                  <Input
                    value={editingRate.insurance_url || ''}
                    onChange={(e) => setEditingRate({ ...editingRate, insurance_url: e.target.value })}
                    className="bg-white border-gray-100 text-gray-900"
                    placeholder="https://..."
                  />
                </div>

                <div className="space-y-2">
                  <Label className="text-gray-400 text-xs uppercase tracking-wider font-black">{lang === 'ja' ? '国際ゾーン料金 (JSON)' : 'International Zone Rates (JSON)'}</Label>
                  <textarea
                    value={editingRate.international_zones || ''}
                    onChange={(e) => setEditingRate({ ...editingRate, international_zones: e.target.value })}
                    className="w-full h-24 bg-white border-gray-100 rounded-md p-2 text-xs font-mono text-gray-900 focus:ring-orange-400/50"
                    placeholder='{"Asia": 1400, "North America": 2500, ...}'
                  />
                  <p className="text-[10px] text-gray-500">
                    Zones: Asia, North America, Europe, Oceania, South America, Africa, Other
                  </p>
                </div>
              </div>
            )}

            <DialogFooter className="border-t border-gray-100 pt-4">
              <Button
                variant="outline"
                onClick={() => setEditingRate(null)}
                className="border-gray-200 hover:bg-gray-100 text-gray-400"
              >
                <X className="h-4 w-4 mr-2" />
                {t('キャンセル', lang)}
              </Button>
              <Button
                onClick={handleSave}
                disabled={isSaving}
                className="bg-orange-500 hover:bg-orange-600 text-white font-bold"
              >
                <Save className={`h-4 w-4 mr-2 ${isSaving ? 'animate-spin' : ''}`} />
                {t('保存', lang)}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}
