'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft, RefreshCw, UserRound } from 'lucide-react'
import { useBackendAuth } from '@/hooks/useBackendAuth'
import { useAuthStore } from '@/store/auth'
import { authApi } from '@/lib/api'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { toast } from '@/lib/use-toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

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

export default function MypageProfilePage() {
  const router = useRouter()
  const { isLoggedIn, isReady, user, requireAuth } = useBackendAuth()
  const { fetchMe } = useAuthStore()
  const { lang } = useLangStore()

  const [familyName, setFamilyName] = useState('')
  const [givenName, setGivenName] = useState('')
  const [familyNameKana, setFamilyNameKana] = useState('')
  const [givenNameKana, setGivenNameKana] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [birthDate, setBirthDate] = useState('')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [postalCode, setPostalCode] = useState('')
  const [region, setRegion] = useState('')
  const [city, setCity] = useState('')
  const [addressLine1, setAddressLine1] = useState('')
  const [addressLine2, setAddressLine2] = useState('')
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
    setFamilyName(user.family_name || '')
    setGivenName(user.given_name || '')
    setFamilyNameKana(user.family_name_kana || '')
    setGivenNameKana(user.given_name_kana || '')
    setDisplayName(user.name || '')
    setBirthDate(user.birth_date || '')
    setPhoneNumber(user.phone_number || '')
    setPostalCode(user.postal_code || '')
    setRegion(user.region || '')
    setCity(user.city || '')
    setAddressLine1(user.address_line1 || '')
    setAddressLine2(user.address_line2 || '')
  }, [user])

  useEffect(() => {
    const fetchAddress = async () => {
      const cleanZip = postalCode.replace(/[^\d]/g, '')
      if (cleanZip.length !== 7) return
      setIsFetchingAddress(true)
      try {
        const res = await fetch(`https://zipcloud.ibsnet.co.jp/api/search?zipcode=${cleanZip}`)
        const data = await res.json()
        if (data.results?.[0]) {
          const result = data.results[0]
          setRegion(result.address1 || '')
          setCity(result.address2 || '')
          setAddressLine1(result.address3 || '')
        }
      } catch {
        // ignore lookup failures
      } finally {
        setIsFetchingAddress(false)
      }
    }
    void fetchAddress()
  }, [postalCode])

  const handleSave = async () => {
    if (!familyName.trim() || !givenName.trim()) {
      toast({
        title: t('エラー', lang),
        description: '氏名（姓・名）を入力してください。',
        variant: 'destructive',
      })
      return
    }
    if (!birthDate) {
      toast({
        title: t('エラー', lang),
        description: '生年月日を入力してください。',
        variant: 'destructive',
      })
      return
    }

    setIsSaving(true)
    try {
      await authApi.updateProfile({
        family_name: familyName.trim(),
        given_name: givenName.trim(),
        family_name_kana: familyNameKana.trim() || undefined,
        given_name_kana: givenNameKana.trim() || undefined,
        name: displayName.trim() || `${familyName.trim()} ${givenName.trim()}`.trim(),
        birth_date: birthDate,
        phone_number: phoneNumber.trim() || undefined,
        postal_code: postalCode.trim() || undefined,
        country: 'JP',
        region: region.trim() || undefined,
        city: city.trim() || undefined,
        address_line1: addressLine1.trim() || undefined,
        address_line2: addressLine2.trim() || undefined,
      })
      await fetchMe()
      toast({
        title: t('保存しました', lang),
        description: 'お客様情報を更新しました。',
      })
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '保存に失敗しました'
      toast({
        title: t('エラー', lang),
        description: message,
        variant: 'destructive',
      })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      <div className="mx-auto max-w-2xl px-4 py-8">
        <Link href="/mypage" className="mb-6 inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900">
          <ArrowLeft className="h-4 w-4" />
          {t('マイページに戻る', lang)}
        </Link>

        <div className="mb-6 flex items-center gap-3">
          <div className="rounded-full bg-indigo-100 p-3 text-indigo-700">
            <UserRound className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">お客様情報</h1>
            <p className="text-sm text-gray-500">本人確認に使用する基本情報を登録・編集できます。</p>
          </div>
        </div>

        <div className="space-y-6 rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <section className="space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">基本情報</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="familyName">氏名（姓）</Label>
                <Input id="familyName" value={familyName} onChange={(e) => setFamilyName(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="givenName">氏名（名）</Label>
                <Input id="givenName" value={givenName} onChange={(e) => setGivenName(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="familyNameKana">フリガナ（セイ）</Label>
                <Input id="familyNameKana" value={familyNameKana} onChange={(e) => setFamilyNameKana(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="givenNameKana">フリガナ（メイ）</Label>
                <Input id="givenNameKana" value={givenNameKana} onChange={(e) => setGivenNameKana(e.target.value)} />
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="displayName">ニックネーム（表示名）</Label>
                <Input id="displayName" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="birthDate">生年月日</Label>
                <Input id="birthDate" type="date" value={birthDate} onChange={(e) => setBirthDate(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="phoneNumber">電話番号</Label>
                <Input id="phoneNumber" value={phoneNumber} onChange={(e) => setPhoneNumber(e.target.value)} />
              </div>
            </div>
          </section>

          <section className="space-y-4 border-t border-gray-100 pt-6">
            <h2 className="text-lg font-semibold text-gray-900">住所</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="postalCode">郵便番号</Label>
                <div className="flex gap-2">
                  <Input id="postalCode" value={postalCode} onChange={(e) => setPostalCode(e.target.value)} placeholder="1234567" />
                  {isFetchingAddress && <RefreshCw className="mt-2 h-5 w-5 animate-spin text-gray-400" />}
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="region">都道府県</Label>
                <select
                  id="region"
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                >
                  <option value="">選択してください</option>
                  {PREFECTURES.map((pref) => (
                    <option key={pref} value={pref}>
                      {pref}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="city">市区町村</Label>
                <Input id="city" value={city} onChange={(e) => setCity(e.target.value)} />
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="addressLine1">番地</Label>
                <Input id="addressLine1" value={addressLine1} onChange={(e) => setAddressLine1(e.target.value)} />
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="addressLine2">建物名・部屋番号（任意）</Label>
                <Input id="addressLine2" value={addressLine2} onChange={(e) => setAddressLine2(e.target.value)} />
              </div>
            </div>
          </section>

          <Button className="w-full" onClick={handleSave} disabled={isSaving}>
            {isSaving ? '保存中...' : '保存する'}
          </Button>
        </div>
      </div>
    </div>
  )
}
