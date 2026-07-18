'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft, MapPin, RefreshCw } from 'lucide-react'
import { useBackendAuth } from '@/hooks/useBackendAuth'
import { useAuthStore } from '@/store/auth'
import { authApi } from '@/lib/api'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { toast } from '@/lib/use-toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

import { CHECKOUT_COUNTRIES, countryDisplayName, normalizeCountryCode } from '@/lib/country'

const PREFECTURES = [
  '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
  '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
  '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県',
  '岐阜県', '静岡県', '愛知県', '三重県',
  '滋賀県', '京都府', '大阪府', '兵庫県', '奈良県', '和歌山県',
  '鳥取県', '島根県', '岡山県', '広島県', '山口県',
  '徳島県', '香川県', '愛媛県', '高知県',
  '福岡県', '佐賀県', '長崎県', '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県',
]

export default function AddressesPage() {
  const router = useRouter()
  const { isLoggedIn, isReady, user, requireAuth } = useBackendAuth()
  const { fetchMe } = useAuthStore()
  const { lang } = useLangStore()

  const [postalCode, setPostalCode] = useState('')
  const [country, setCountry] = useState('JP')
  const [region, setRegion] = useState('')
  const [city, setCity] = useState('')
  const [addressLine1, setAddressLine1] = useState('')
  const [addressLine2, setAddressLine2] = useState('')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [isFetchingAddress, setIsFetchingAddress] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  useEffect(() => {
    if (!isMounted || !isReady) return
    if (!isLoggedIn) {
      router.push('/sign-in')
      return
    }
    void requireAuth().then((token) => {
      if (token) fetchMe()
    })
  }, [isMounted, isReady, isLoggedIn, router, fetchMe, requireAuth])

  useEffect(() => {
    if (!user) return
    setPostalCode(user.postal_code || '')
    setCountry(normalizeCountryCode(user.country))
    setRegion(user.region || '')
    setCity(user.city || '')
    setAddressLine1(user.address_line1 || '')
    setAddressLine2(user.address_line2 || '')
    setPhoneNumber(user.phone_number || '')
  }, [user])

  useEffect(() => {
    const fetchAddress = async () => {
      const cleanZip = postalCode.replace(/[^\d]/g, '')
      if (cleanZip.length !== 7 || country !== 'JP') return
      setIsFetchingAddress(true)
      try {
        const res = await fetch(`https://zipcloud.ibsnet.co.jp/api/search?zipcode=${cleanZip}`)
        const data = await res.json()
        if (data.status === 200 && data.results?.[0]) {
          const result = data.results[0]
          setRegion(result.address1)
          setCity(result.address2 + result.address3)
          toast({
            title: lang === 'ja' ? '住所を自動入力しました' : 'Address auto-filled',
          })
        }
      } catch {
        // ignore
      } finally {
        setIsFetchingAddress(false)
      }
    }
    fetchAddress()
  }, [postalCode, country, lang])

  const handleSave = async () => {
    setIsSaving(true)
    try {
      const token = await requireAuth()
      if (!token) {
        router.push('/sign-in')
        return
      }
      await authApi.updateProfile({
        postal_code: postalCode,
        country: country,
        region,
        city,
        address_line1: addressLine1,
        address_line2: addressLine2,
        phone_number: phoneNumber || undefined,
      })
      await fetchMe()
      toast({ title: t('住所を保存しました', lang) })
    } catch {
      toast({
        title: t('エラー', lang),
        description: t('住所の保存に失敗しました', lang),
        variant: 'destructive',
      })
    } finally {
      setIsSaving(false)
    }
  }

  if (!isMounted || !isReady || !isLoggedIn) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-2xl">
        <Link
          href="/mypage"
          className="inline-flex items-center gap-2 text-gray-400 hover:text-gray-900 mb-6 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('マイページ', lang)}
        </Link>

        <h1 className="text-2xl font-bold text-gray-900 mb-2 flex items-center gap-2">
          <MapPin className="h-6 w-6 text-blue-400" />
          {t('住所管理', lang)}
        </h1>
        <p className="text-sm text-gray-500 mb-8">{t('配送先住所を登録・編集できます', lang)}</p>

        <div className="bg-gray-50 rounded-xl border border-gray-200 p-6 space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="postalCode">{t('郵便番号', lang)}</Label>
              <div className="relative mt-1">
                <Input
                  id="postalCode"
                  value={postalCode}
                  onChange={(e) => setPostalCode(e.target.value)}
                  placeholder="123-4567"
                />
                {isFetchingAddress && (
                  <RefreshCw className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 animate-spin" />
                )}
              </div>
            </div>
            <div>
              <Label htmlFor="country">{t('国', lang)}</Label>
              <select
                id="country"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="mt-1 w-full h-10 rounded-md border border-gray-300 bg-white px-3 text-sm"
              >
                {CHECKOUT_COUNTRIES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {lang === 'ja' ? c.ja : c.en}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {country === 'JP' ? (
            <div>
              <Label htmlFor="region">{t('都道府県', lang)}</Label>
              <select
                id="region"
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                className="mt-1 w-full h-10 rounded-md border border-gray-300 bg-white px-3 text-sm"
              >
                <option value="">{lang === 'ja' ? '選択してください' : 'Select'}</option>
                {PREFECTURES.map((pref) => (
                  <option key={pref} value={pref}>
                    {t(pref, lang)}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div>
              <Label htmlFor="region">{t('州・省', lang)}</Label>
              <Input id="region" value={region} onChange={(e) => setRegion(e.target.value)} className="mt-1" />
            </div>
          )}

          <div>
            <Label htmlFor="city">{t('市区町村', lang)}</Label>
            <Input id="city" value={city} onChange={(e) => setCity(e.target.value)} className="mt-1" />
          </div>

          <div>
            <Label htmlFor="addressLine1">{t('住所番地', lang)}</Label>
            <Input id="addressLine1" value={addressLine1} onChange={(e) => setAddressLine1(e.target.value)} className="mt-1" />
          </div>

          <div>
            <Label htmlFor="addressLine2">{t('建物名・部屋番号（任意）', lang)}</Label>
            <Input id="addressLine2" value={addressLine2} onChange={(e) => setAddressLine2(e.target.value)} className="mt-1" />
          </div>

          <div>
            <Label htmlFor="phoneNumber">{t('電話番号', lang)}</Label>
            <Input id="phoneNumber" value={phoneNumber} onChange={(e) => setPhoneNumber(e.target.value)} className="mt-1" />
          </div>

          <Button
            onClick={handleSave}
            disabled={isSaving}
            className="w-full bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold"
          >
            {isSaving ? t('保存中...', lang) : t('保存', lang)}
          </Button>
        </div>
      </div>
    </div>
  )
}
