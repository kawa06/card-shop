'use client'

import { useState, useEffect } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/auth'
import { useCartStore } from '@/store/cart'
import { ordersApi, authApi, shippingApi } from '@/lib/api'
import { toast } from '@/lib/use-toast'
import { formatPrice, usePrice } from '@/lib/format'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { useTranslation } from '@/hooks/useTranslation'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ShippingRate } from '@/lib/types'
import { Smartphone, CheckCircle2 } from 'lucide-react'

const PREFECTURES = [
  "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
  "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
  "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
  "岐阜県", "静岡県", "愛知県", "三重県",
  "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
  "鳥取県", "島根県", "岡山県", "広島県", "山口県",
  "徳島県", "香川県", "愛媛県", "高知県",
  "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"
];

export default function CheckoutPage() {
  const router = useRouter()
  const { isAuthenticated, user, isLoading: isAuthLoading, fetchMe } = useAuthStore()
  const { items, total, fetchCart, clearCart } = useCartStore()
  const { formatPrice } = usePrice()
  const { lang } = useLangStore()
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const [postalCode, setPostalCode] = useState('')
  const [country, setCountry] = useState('Japan')
  const [region, setRegion] = useState('')
  const [city, setCity] = useState('')
  const [addressLine1, setAddressLine1] = useState('')
  const [addressLine2, setAddressLine2] = useState('')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [fullName, setFullName] = useState('')
  const [isFetchingAddress, setIsFetchingAddress] = useState(false)

  // Fetch address from zipcloud when postal code is 7 digits
  useEffect(() => {
    const fetchAddress = async () => {
      const cleanZip = postalCode.replace(/[^\d]/g, '')
      if (cleanZip.length === 7) {
        setIsFetchingAddress(true)
        try {
          const res = await fetch(`https://zipcloud.ibsnet.co.jp/api/search?zipcode=${cleanZip}`)
          const data = await res.json()
          if (data.status === 200 && data.results && data.results[0]) {
            const result = data.results[0]
            setRegion(result.address1)
            setCity(result.address2 + result.address3)
            toast({
              title: lang === 'ja' ? '住所を自動入力しました' : 'Address auto-filled',
              description: `${result.address1}${result.address2}${result.address3}`
            })
          } else if (data.message) {
             console.error('Zipcloud API error:', data.message)
          }
        } catch (error) {
          console.error('Failed to fetch address', error)
        } finally {
          setIsFetchingAddress(false)
        }
      }
    }

    // Only auto-fetch for Japan
    if (lang === 'ja' || country === 'Japan') {
      fetchAddress()
    }
  }, [postalCode, lang, country])

  // Debounced address state for shipping calculation
  const [debouncedAddress, setDebouncedAddress] = useState({ region: '', country: 'Japan' })
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedAddress({ region, country })
    }, 300)
    return () => clearTimeout(timer)
  }, [region, country])

  const [paymentMethod, setPaymentMethod] = useState('credit_card')
  const [shippingRates, setShippingRates] = useState<ShippingRate[]>([])
  const [shippingMethod, setShippingMethod] = useState('')
  const [dynamicShippingFee, setDynamicShippingFee] = useState<number | null>(null)
  const [agreedToNoCompensation, setAgreedToNoCompensation] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [saveAddress, setSaveAddress] = useState(true)

  // Phone verification state
  const [otpCode, setOtpCode] = useState('')
  const [isSendingOtp, setIsSendingOtp] = useState(false)
  const [isVerifyingOtp, setIsVerifyingOtp] = useState(false)
  const [showOtpInput, setShowOtpInput] = useState(false)
  const [isDebugMode, setIsDebugMode] = useState(false)

  const normalizePhone = (raw: string) => {
    const cleaned = raw.trim().replace(/[\s-]/g, '')
    if (cleaned.startsWith('0') && cleaned.length > 0) {
      return '+81' + cleaned.slice(1)
    }
    return cleaned
  }

  const handleSendOtp = async () => {
    if (!phoneNumber.trim()) {
      toast({ title: t('エラー', lang), description: t('電話番号を入力してください', lang), variant: 'destructive' })
      return
    }
    setIsSendingOtp(true)
    try {
      const normalizedPhone = normalizePhone(phoneNumber)
      const res = await authApi.sendPhoneOtp(normalizedPhone)
      setIsDebugMode(res.data.debug || false)
      toast({
        title: lang === 'ja' ? '送信しました' : 'Sent',
        description: res.data.debug
          ? 'SMSをご確認ください（デモ環境: 認証コードは 000000）'
          : 'SMSをご確認ください / SMS sent'
      })
      setShowOtpInput(true)
    } catch (err: any) {
      toast({
        title: t('エラー', lang),
        description: err.response?.data?.detail || t('SMS送信に失敗しました', lang),
        variant: 'destructive'
      })
    } finally {
      setIsSendingOtp(false)
    }
  }

  const handleVerifyOtp = async () => {
    if (!otpCode.trim() || otpCode.length !== 6) {
      toast({ title: t('エラー', lang), description: t('6桁のコードを入力', lang), variant: 'destructive' })
      return
    }
    setIsVerifyingOtp(true)
    try {
      const normalizedPhone = normalizePhone(phoneNumber)
      await authApi.verifyPhoneOtp(normalizedPhone, otpCode)
      toast({ title: t('認証に成功しました', lang), description: t('電話番号の認証が完了しました', lang) })
      setShowOtpInput(false)
      fetchMe()
    } catch (err: any) {
      toast({ 
        title: t('エラー', lang), 
        description: err.response?.data?.detail || t('認証に失敗しました', lang), 
        variant: 'destructive' 
      })
    } finally {
      setIsVerifyingOtp(false)
    }
  }

  const isInternational = country !== 'Japan' && country !== ''
  
  // Fetch shipping rates
  useEffect(() => {
    if (!isMounted) return
    shippingApi.getRates().then(res => {
      setShippingRates(res.data)
    })
  }, [isMounted])

  // Calculate allowed shipping methods intersection
  const allowedMethodCodes = (() => {
    if (!items.length) return null
    let intersection: Set<string> | null = null
    
    for (const item of items) {
      if (item.card.allowed_shipping_methods) {
        try {
          // Handle various empty states like "null", "[]", ""
          const raw = item.card.allowed_shipping_methods
          if (raw === 'null' || raw === '[]' || raw === '') continue

          const methods = JSON.parse(raw)
          if (Array.isArray(methods) && methods.length > 0) {
            const methodSet = new Set(methods)
            if (intersection === null) {
              intersection = methodSet
            } else {
              intersection = new Set(Array.from(intersection).filter(x => methodSet.has(x)))
            }
          }
        } catch (e) {
          console.error('Failed to parse allowed_shipping_methods', e)
        }
      }
    }
    return intersection ? Array.from(intersection) : null
  })()

  const availableRates = shippingRates.filter(rate => {
    // Yamato Compact and Click Post are always shown regardless of the individual flag
    const isAlwaysShown = rate.method_code === 'takkyubin_compact' || rate.method_code === 'click_post'
    
    // For others, check if it's available for individuals
    if (!isAlwaysShown && !rate.is_individual_available) return false

    if (isInternational) {
      return rate.method_code === 'international'
    }
    if (rate.method_code === 'international') return false

    if (allowedMethodCodes === null) return true
    return allowedMethodCodes.includes(rate.method_code)
  })

  // Auto-select first available shipping method
  useEffect(() => {
    if (availableRates.length > 0 && !shippingMethod) {
      // Prefer Takkyubin Compact if available
      const preferred = availableRates.find(r => r.method_code === 'takkyubin_compact')
      setShippingMethod(preferred ? preferred.method_code : availableRates[0].method_code)
    }
  }, [availableRates, shippingMethod])

  // Fetch dynamic shipping fee when method or destination changes
  useEffect(() => {
    if (!shippingMethod) {
      setDynamicShippingFee(null)
      return
    }

    // New API format: ?method=xxx&prefecture=yyy
    shippingApi.calculateRate({
      method: shippingMethod,
      prefecture: debouncedAddress.region
    }).then(res => {
      setDynamicShippingFee(res.data.fee)
    }).catch(() => {
      // Fallback to static rate
      const selectedRate = shippingRates.find(r => r.method_code === shippingMethod)
      setDynamicShippingFee(selectedRate?.fee_jpy || 0)
    })
  }, [shippingMethod, debouncedAddress, shippingRates])

  const selectedRate = shippingRates.find(r => r.method_code === shippingMethod)
  const shippingFee = dynamicShippingFee ?? (isInternational ? 0 : (selectedRate?.fee_jpy || 0))
  const finalTotal = total + shippingFee

  // Grouped shipping rates
  const groupedRates = availableRates.reduce((acc, rate) => {
    const carrier = rate.carrier || 'other'
    if (!acc[carrier]) acc[carrier] = []
    acc[carrier].push(rate)
    return acc
  }, {} as Record<string, ShippingRate[]>)

  const needsCompensationAgreement = selectedRate && !selectedRate.has_insurance

  // Pre-fill address if available
  useEffect(() => {
    if (user) {
      if (user.postal_code) setPostalCode(user.postal_code)
      if (user.country) setCountry(user.country || 'Japan')
      if (user.region) setRegion(user.region)
      if (user.city) setCity(user.city)
      if (user.address_line1) setAddressLine1(user.address_line1)
      if (user.address_line2) setAddressLine2(user.address_line2)
      if (user.phone_number) setPhoneNumber(user.phone_number)
      if (user.name) setFullName(user.name)
    }
  }, [user])

  useEffect(() => {
    if (!isMounted || isAuthLoading) return

    if (!isAuthenticated) {
      router.push('/login')
      return
    }
    fetchCart()
  }, [isMounted, isAuthLoading, isAuthenticated, router, fetchCart])

  useEffect(() => {
    if (!isMounted || isAuthLoading || !isAuthenticated) return
    if (items.length === 0 && !isAuthLoading) {
      router.push('/cart')
    }
  }, [items, isMounted, isAuthLoading, isAuthenticated, router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validation
    if (!postalCode.trim()) {
      toast({ title: t('エラー', lang), description: t('郵便番号を入力してください', lang), variant: 'destructive' })
      return
    }
    if (!region.trim()) {
      toast({ title: t('エラー', lang), description: t('都道府県を入力してください', lang), variant: 'destructive' })
      return
    }
    if (!city.trim()) {
      toast({ title: t('エラー', lang), description: t('市区町村を入力してください', lang), variant: 'destructive' })
      return
    }
    if (!addressLine1.trim()) {
      toast({ title: t('エラー', lang), description: t('住所番地を入力してください', lang), variant: 'destructive' })
      return
    }
    if (lang === 'en' && !fullName.trim()) {
      toast({ title: t('エラー', lang), description: 'Please enter full name', variant: 'destructive' })
      return
    }

    if (!phoneNumber.trim()) {
      toast({ title: t('エラー', lang), description: t('電話番号を入力してください', lang), variant: 'destructive' })
      return
    }

    if (!isInternational && needsCompensationAgreement && !agreedToNoCompensation) {
      toast({ title: t('エラー', lang), description: t('補償が無いことに同意します', lang), variant: 'destructive' })
      return
    }

    if (!isInternational && !shippingMethod) {
      toast({ title: t('エラー', lang), description: t('発送方法を選択してください', lang), variant: 'destructive' })
      return
    }

    if (!isInternational && availableRates.length === 0) {
      toast({ title: t('エラー', lang), description: t('利用可能な発送方法がありません', lang), variant: 'destructive' })
      return
    }

    setIsSubmitting(true)
    try {
      const normalizedPhone = normalizePhone(phoneNumber)
      const currentCountry = lang === 'ja' ? 'Japan' : country
      const shippingAddress = lang === 'ja'
        ? `〒${postalCode} ${region}${city}${addressLine1} ${addressLine2} (Tel: ${normalizedPhone})`
        : `${fullName}, ${addressLine1}, ${addressLine2 ? addressLine2 + ', ' : ''}${city}, ${region} ${postalCode}, ${currentCountry} (Tel: ${normalizedPhone})`

      // 1. Update user profile if saveAddress is checked
      if (saveAddress) {
        await authApi.updateProfile({ 
          name: lang === 'en' ? fullName : user?.name,
          postal_code: postalCode,
          country: currentCountry,
          region: region,
          city: city,
          address_line1: addressLine1,
          address_line2: addressLine2,
          phone_number: normalizedPhone
        })
        fetchMe() // refresh global state
      }

      // 2. Create order
      const res = await ordersApi.create({
        postal_code: postalCode,
        country: currentCountry,
        region: region,
        city: city,
        address_line1: addressLine1,
        address_line2: addressLine2,
        shipping_address: shippingAddress,
        shipping_method: isInternational ? 'international' : shippingMethod,
        shipping_fee: shippingFee,
        payment_method: paymentMethod,
      })
      
      clearCart()
      toast({ title: t('注文が完了しました！', lang), description: `${t('注文番号', lang)}: #${res.data.id}` })
      router.push('/orders')
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (lang === 'ja' ? '注文に失敗しました。もう一度お試しください。' : 'Failed to place order. Please try again.')
      toast({ title: t('エラー', lang), description: message, variant: 'destructive' })
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isMounted || isAuthLoading || !isAuthenticated || items.length === 0) return null

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="container py-8 max-w-2xl">
        <h1 className="text-2xl font-bold text-white mb-6 text-center">{t('注文確認', lang)}</h1>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* 1. 配送先住所 */}
          <section className="bg-gray-900 rounded-lg border border-white/10 p-5 space-y-4">
            <h2 className="text-white font-semibold flex items-center gap-2">
              <span className="flex items-center justify-center w-6 h-6 rounded-full bg-yellow-400 text-gray-950 text-xs font-bold">1</span>
              {t('配送先住所', lang)}
            </h2>
            <div className="grid grid-cols-1 gap-4">
                {lang === 'en' ? (
                  <>
                    <div className="space-y-2">
                      <Label htmlFor="country" className="text-gray-300 text-sm">{t('国', lang)}</Label>
                      <select
                        id="country"
                        value={country}
                        onChange={(e) => setCountry(e.target.value)}
                        required
                        className="w-full h-10 px-3 bg-gray-800 border border-gray-700 rounded-md text-white focus:ring-yellow-400/50"
                      >
                        <option value="">{t('国を選択してください', lang)}</option>
                        <option value="United States">{t('アメリカ合衆国', lang)}</option>
                        <option value="United Kingdom">{t('イギリス', lang)}</option>
                        <option value="Canada">{t('カナダ', lang)}</option>
                        <option value="Australia">{t('オーストラリア', lang)}</option>
                        <option value="Other">{t('その他', lang)}</option>
                      </select>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="fullName" className="text-gray-300 text-sm">{t('氏名', lang)}</Label>
                      <Input
                        id="fullName"
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        placeholder="John Doe"
                        required
                        className="bg-gray-800 border-gray-700 text-white focus:ring-yellow-400/50"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="addressLine1" className="text-gray-300 text-sm">{t('住所番地', lang)}</Label>
                      <Input
                        id="addressLine1"
                        value={addressLine1}
                        onChange={(e) => setAddressLine1(e.target.value)}
                        placeholder="123 Main St"
                        required
                        className="bg-gray-800 border-gray-700 text-white focus:ring-yellow-400/50"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="addressLine2" className="text-gray-300 text-sm">{t('建物名・部屋番号（任意）', lang)}</Label>
                      <Input
                        id="addressLine2"
                        value={addressLine2}
                        onChange={(e) => setAddressLine2(e.target.value)}
                        placeholder="Apt 101"
                        className="bg-gray-800 border-gray-700 text-white focus:ring-yellow-400/50"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="city" className="text-gray-300 text-sm">{t('市区町村', lang)}</Label>
                      <Input
                        id="city"
                        value={city}
                        onChange={(e) => setCity(e.target.value)}
                        placeholder="New York"
                        required
                        className="bg-gray-800 border-gray-700 text-white focus:ring-yellow-400/50"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="region" className="text-gray-300 text-sm">{t('都道府県', lang)}</Label>
                      <Input
                        id="region"
                        value={region}
                        onChange={(e) => setRegion(e.target.value)}
                        placeholder="NY"
                        required
                        className="bg-gray-800 border-gray-700 text-white focus:ring-yellow-400/50"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="postalCode" className="text-gray-300 text-sm">{t('郵便番号', lang)}</Label>
                      <Input
                        id="postalCode"
                        value={postalCode}
                        onChange={(e) => setPostalCode(e.target.value)}
                        placeholder="10001"
                        required
                        className="bg-gray-800 border-gray-700 text-white focus:ring-yellow-400/50"
                      />
                    </div>
                  </>
                ) : (
                  <>
                    <div className="space-y-2">
                      <Label htmlFor="postalCode" className="text-gray-300 text-sm">{t('郵便番号', lang)}</Label>
                      <Input
                        id="postalCode"
                        value={postalCode}
                        onChange={(e) => setPostalCode(e.target.value)}
                        placeholder="000-0000"
                        required
                        className="bg-gray-800 border-gray-700 text-white focus:ring-yellow-400/50"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="region" className="text-gray-300 text-sm">{t('都道府県', lang)}</Label>
                      <select
                        id="region"
                        value={region}
                        onChange={(e) => setRegion(e.target.value)}
                        required
                        className="w-full h-10 px-3 bg-gray-800 border-gray-700 rounded-md text-white focus:ring-yellow-400/50"
                      >
                        <option value="">{t('都道府県を入力してください', lang)}</option>
                        {PREFECTURES.map(p => (
                          <option key={p} value={p}>{p}</option>
                        ))}
                      </select>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="city" className="text-gray-300 text-sm">{t('市区町村', lang)}</Label>
                      <Input
                        id="city"
                        value={city}
                        onChange={(e) => setCity(e.target.value)}
                        placeholder="渋谷区"
                        required
                        className="bg-gray-800 border-gray-700 text-white focus:ring-yellow-400/50"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="addressLine1" className="text-gray-300 text-sm">{t('住所番地', lang)}</Label>
                      <Input
                        id="addressLine1"
                        value={addressLine1}
                        onChange={(e) => setAddressLine1(e.target.value)}
                        placeholder="神南1-1-1"
                        required
                        className="bg-gray-800 border-gray-700 text-white focus:ring-yellow-400/50"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="addressLine2" className="text-gray-300 text-sm">{t('建物名・部屋番号（任意）', lang)}</Label>
                      <Input
                        id="addressLine2"
                        value={addressLine2}
                        onChange={(e) => setAddressLine2(e.target.value)}
                        placeholder="〇〇ビル 101"
                        className="bg-gray-800 border-gray-700 text-white focus:ring-yellow-400/50"
                      />
                    </div>
                  </>
                )}
                <div className="flex items-center gap-2 pt-2">
                  <input
                    type="checkbox"
                    id="saveAddress"
                    checked={saveAddress}
                    onChange={(e) => setSaveAddress(e.target.checked)}
                    className="w-4 h-4 rounded border-gray-700 bg-gray-800 text-yellow-400 focus:ring-yellow-400"
                  />
                  <Label htmlFor="saveAddress" className="text-gray-400 text-xs cursor-pointer">
                    {t('この住所を保存して次回から自動入力する', lang)}
                  </Label>
                </div>
            </div>
          </section>

          {/* 2. 連絡先 */}
          <section className="bg-gray-900 rounded-lg border border-white/10 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-white font-semibold flex items-center gap-2">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-yellow-400 text-gray-950 text-xs font-bold">2</span>
                {t('連絡先', lang)}
              </h2>
              {user?.phone_verified && (
                <span className="flex items-center gap-1 text-[10px] bg-green-500/20 text-green-400 px-2 py-0.5 rounded border border-green-500/20">
                  <CheckCircle2 className="h-3 w-3" /> {t('認証済み', lang)}
                </span>
              )}
            </div>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="phoneNumber" className="text-gray-300 text-sm">{t('電話番号', lang)}</Label>
                <div className="flex gap-2">
                  <Input
                    id="phoneNumber"
                    type="tel"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    placeholder={lang === 'en' ? "+1-000-000-0000" : "090-0000-0000"}
                    required
                    className="bg-gray-800 border-gray-700 text-white focus:ring-yellow-400/50 flex-1"
                  />
                  {!user?.phone_verified && (
                    <Button
                      type="button"
                      onClick={handleSendOtp}
                      disabled={isSendingOtp}
                      className="bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold px-4"
                    >
                      {isSendingOtp ? '...' : t('SMS送信', lang)}
                    </Button>
                  )}
                </div>
                {user?.phone_verified && user.phone_number !== normalizePhone(phoneNumber) && (
                  <p className="text-[10px] text-yellow-400/70">
                    ⚠️ {lang === 'ja' ? '登録済みの番号と異なります。再認証が必要です。' : 'Different from registered number. Re-verification required.'}
                  </p>
                )}
              </div>

              {showOtpInput && !user?.phone_verified && (
                <div className="p-4 bg-gray-800/50 border border-white/5 rounded-lg space-y-3 animate-in fade-in slide-in-from-top-2">
                  <Label className="text-gray-300 text-xs">{t('認証コード', lang)}</Label>
                  <div className="flex gap-2">
                    <Input
                      type="text"
                      value={otpCode}
                      onChange={(e) => setOtpCode(e.target.value)}
                      placeholder="6桁のコード"
                      maxLength={6}
                      className="bg-gray-900 border-gray-700 text-white h-10 flex-1"
                    />
                    <Button
                      type="button"
                      onClick={handleVerifyOtp}
                      disabled={isVerifyingOtp}
                      className="bg-white text-gray-950 hover:bg-white/90 font-bold px-6"
                    >
                      {isVerifyingOtp ? '...' : t('認証する', lang)}
                    </Button>
                  </div>
                  {isDebugMode && (
                    <p className="text-[10px] text-gray-500">デモ環境: 認証コードは 000000</p>
                  )}
                </div>
              )}
            </div>
          </section>

          {/* 3. 発送方法 */}
          <section className="bg-gray-900 rounded-lg border border-white/10 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-white font-semibold flex items-center gap-2">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-yellow-400 text-gray-950 text-xs font-bold">3</span>
                {t('発送方法', lang)}
              </h2>
              <Link href="/shipping-policy" className="text-xs text-yellow-400 hover:underline">
                {t('補償について詳しく', lang)}
              </Link>
            </div>

            <div className="space-y-4">
              {!isInternational && allowedMethodCodes && (
                  <p className="text-[10px] text-yellow-400/70 bg-yellow-400/5 p-2 rounded border border-yellow-400/10 italic">
                    ⚠️ {t('カート内商品により発送方法が制限されています', lang)}
                  </p>
                )}
                
                {availableRates.length === 0 ? (
                  <p className="text-xs text-red-400 p-2 bg-red-400/10 rounded border border-red-400/20">
                    {t('利用可能な発送方法がありません。商品の組み合わせをご確認ください。', lang)}
                  </p>
                ) : (
                  Object.entries(groupedRates).map(([carrier, rates]) => (
                    <div key={carrier} className="space-y-2">
                      <h3 className="text-[10px] uppercase tracking-wider text-gray-500 font-bold ml-1">
                        {carrier === 'yamato' ? t('ヤマト運輸', lang) : carrier === 'japan_post' ? t('日本郵便', lang) : t('その他', lang)}
                      </h3>
                      <div className="grid gap-2">
                        {rates.map(rate => (
                          <label 
                            key={rate.method_code}
                            className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${shippingMethod === rate.method_code ? 'bg-yellow-400/5 border-yellow-400/50' : 'bg-gray-800/50 border-white/5 hover:border-white/10'}`}
                          >
                            <input
                              type="radio"
                              name="shipping"
                              value={rate.method_code}
                              checked={shippingMethod === rate.method_code}
                              onChange={() => setShippingMethod(rate.method_code)}
                              className="mt-1 accent-yellow-400"
                            />
                            <div className="flex-1">
                              <p className="text-white text-xs font-bold">
                                {lang === 'ja' ? rate.name_ja : rate.name_en}
                                <span className="ml-2 text-[10px] font-normal text-gray-500">
                                  [{rate.has_tracking ? t('追跡有', lang) : t('追跡無', lang)}] 
                                  [{rate.has_insurance ? t('補償有', lang) : t('補償無', lang)}]
                                </span>
                              </p>
                              <p className="text-gray-400 text-[10px]">
                                {formatPrice(rate.fee_jpy)}
                              </p>
                            </div>
                          </label>
                        ))}
                      </div>
                    </div>
                  ))
                )}
            </div>
          </section>

          {/* 4. 注文サマリ */}
          <section className="bg-gray-900 rounded-lg border border-white/10 p-5 space-y-4">
            <h2 className="text-white font-semibold flex items-center gap-2">
              <span className="flex items-center justify-center w-6 h-6 rounded-full bg-yellow-400 text-gray-950 text-xs font-bold">4</span>
              {t('注文内容確認', lang)}
            </h2>
            <div className="space-y-3">
              {items.map((item) => (
                <CheckoutItemRow key={item.id} item={item} formatPrice={formatPrice} lang={lang} />
              ))}
              <div className="border-t border-white/10 pt-3 space-y-1 text-sm">
                <div className="flex justify-between text-gray-400">
                  <span>{t('小計', lang)}</span>
                  <span>{formatPrice(total)}</span>
                </div>
                <div className="flex justify-between text-gray-400">
                  <span>{t('送料', lang)}</span>
                  <span>{formatPrice(shippingFee)}</span>
                </div>
              </div>
              <div className="border-t border-white/10 pt-3 flex justify-between font-bold">
                <span className="text-gray-400">{t('合計', lang)}</span>
                <span className="text-yellow-400 text-lg">{formatPrice(finalTotal)}</span>
              </div>
            </div>
          </section>

          {/* 5. 利用規約・補償免責同意 */}
          {(needsCompensationAgreement || true) && (
            <section className="bg-gray-900 rounded-lg border border-white/10 p-5 space-y-4">
              <h2 className="text-white font-semibold flex items-center gap-2">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-yellow-400 text-gray-950 text-xs font-bold">5</span>
                {t('同意事項', lang)}
              </h2>
              
              <div className="space-y-3">
                <div className="space-y-2">
                  <Label className="text-gray-300 text-sm">{t('支払い方法', lang)}</Label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    {[
                      { value: 'credit_card', label: t('カード', lang) },
                      { value: 'bank_transfer', label: t('銀行振込', lang) },
                      { value: 'cod', label: t('代金引換', lang) },
                    ].map((method) => (
                      <label key={method.value} className={`flex items-center gap-2 p-3 rounded-lg border cursor-pointer transition-colors ${paymentMethod === method.value ? 'bg-yellow-400/5 border-yellow-400/50' : 'bg-gray-800/50 border-white/5'}`}>
                        <input
                          type="radio"
                          name="payment"
                          value={method.value}
                          checked={paymentMethod === method.value}
                          onChange={() => setPaymentMethod(method.value)}
                          className="accent-yellow-400"
                        />
                        <span className="text-gray-300 text-xs">{method.label}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {needsCompensationAgreement && (
                  <div className="p-4 bg-yellow-400/5 border border-yellow-400/20 rounded-lg space-y-3">
                    <p className="text-xs text-gray-300 leading-relaxed">
                      {t('ご希望の発送方法は、万が一の事故（紛失・破損）の際の補償が限定的、またはありません。', lang)}
                      <Link href="/shipping-policy" className="text-yellow-400 hover:underline ml-1">
                        {t('発送・補償ポリシーを確認', lang)}
                      </Link>
                    </p>
                    <label className="flex items-center gap-3 cursor-pointer group">
                      <input
                        type="checkbox"
                        checked={agreedToNoCompensation}
                        onChange={(e) => setAgreedToNoCompensation(e.target.checked)}
                        className="w-4 h-4 rounded border-gray-700 bg-gray-800 text-yellow-400 focus:ring-yellow-400"
                      />
                      <span className="text-sm text-yellow-400 font-bold group-hover:text-yellow-300 transition-colors">
                        {t('配送会社の補償規定および免責事項に同意します', lang)}
                      </span>
                    </label>
                  </div>
                )}
              </div>
            </section>
          )}

          {/* 6. 注文確定ボタン */}
          <div className="pt-4">
            <Button
              type="submit"
              disabled={isSubmitting || (!isInternational && availableRates.length === 0)}
              className="w-full h-14 bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-black text-lg shadow-xl shadow-yellow-400/10"
            >
              {isSubmitting ? t('注文処理中...', lang) : t('注文を確定する', lang)}
            </Button>
            <p className="text-center text-[10px] text-gray-500 mt-4">
              By clicking confirm, you agree to our Terms of Service and Privacy Policy.
            </p>
          </div>
        </form>
      </div>
    </div>
  )
}

function CheckoutItemRow({ item, formatPrice, lang }: any) {
  const cardName = useTranslation(item.card?.name)
  return (
    <div className="flex gap-3 items-center">
      <div className="relative w-12 h-16 flex-shrink-0 rounded overflow-hidden bg-gray-800">
        {item.card?.image_url ? (
          <Image src={item.card.image_url} alt={cardName} fill className="object-cover" />
        ) : (
          <div className="flex items-center justify-center h-full text-xl">🃏</div>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-white text-sm font-medium truncate">{cardName || t('不明なカード', lang)}</p>
        <p className="text-gray-500 text-xs">{item.card?.rarity} × {item.quantity}</p>
      </div>
      <p className="text-yellow-400 font-bold text-sm">
        {formatPrice((item.card?.price || 0) * item.quantity)}
      </p>
    </div>
  )
}
