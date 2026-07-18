'use client'

import { useState, useEffect } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useBackendAuth } from '@/hooks/useBackendAuth'
import { useAuthStore } from '@/store/auth'
import { useCartStore } from '@/store/cart'
import { ordersApi, authApi, shippingApi, paymentsApi } from '@/lib/api'
import { toast } from '@/lib/use-toast'
import { formatPrice, usePrice } from '@/lib/format'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { useTranslation } from '@/hooks/useTranslation'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ShippingRate, User } from '@/lib/types'
import { Badge } from '@/components/ui/badge'
import { Check, ShieldCheck, Truck, ExternalLink, Info, RefreshCw } from 'lucide-react'

const COUNTRIES = [
  { code: 'JP', ja: '日本', en: 'Japan' },
  { code: 'US', ja: 'アメリカ合衆国', en: 'United States' },
  { code: 'CN', ja: '中国', en: 'China' },
  { code: 'KR', ja: '韓国', en: 'South Korea' },
  { code: 'TW', ja: '台湾', en: 'Taiwan' },
  { code: 'HK', ja: '香港', en: 'Hong Kong' },
  { code: 'SG', ja: 'シンガポール', en: 'Singapore' },
  { code: 'TH', ja: 'タイ', en: 'Thailand' },
  { code: 'GB', ja: 'イギリス', en: 'United Kingdom' },
  { code: 'FR', ja: 'フランス', en: 'France' },
  { code: 'DE', ja: 'ドイツ', en: 'Germany' },
  { code: 'IT', ja: 'イタリア', en: 'Italy' },
  { code: 'ES', ja: 'スペイン', en: 'Spain' },
  { code: 'CA', ja: 'カナダ', en: 'Canada' },
  { code: 'AU', ja: 'オーストラリア', en: 'Australia' },
  { code: 'NZ', ja: 'ニュージーランド', en: 'New Zealand' },
];

export default function CheckoutPage() {
  const router = useRouter()
  const { isLoggedIn, isReady, user, requireAuth } = useBackendAuth()
  const { fetchMe } = useAuthStore()
  const { items, total, fetchCart, clearCart } = useCartStore()
  const { formatPrice } = usePrice()
  const { lang } = useLangStore()
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const [postalCode, setPostalCode] = useState('')
  const [country, setCountry] = useState('JP')
  const [region, setRegion] = useState('')
  const [city, setCity] = useState('')
  const [addressLine1, setAddressLine1] = useState('')
  const [addressLine2, setAddressLine2] = useState('')
  const [fullName, setFullName] = useState('')
  const [isFetchingAddress, setIsFetchingAddress] = useState(false)

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

  // Language to Default Country sync
  useEffect(() => {
    if (lang === 'en') {
      setCountry('US')
    } else {
      setCountry('JP')
    }
  }, [lang])

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
    if (country === 'JP') {
      fetchAddress()
    }
  }, [postalCode, lang, country])

  // Debounced address state for shipping calculation
  const [debouncedAddress, setDebouncedAddress] = useState({ region: '', country: 'JP' })
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
  const [agreedToTerms, setAgreedToTerms] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [saveAddress, setSaveAddress] = useState(true)
  const [stripeEnabled, setStripeEnabled] = useState(false)

  const isInternational = country !== 'JP'

  useEffect(() => {
    if (!stripeEnabled && (paymentMethod === 'credit_card' || paymentMethod === 'konbini')) {
      setPaymentMethod('bank_transfer')
    }
  }, [stripeEnabled, paymentMethod])

  useEffect(() => {
    if (isInternational && paymentMethod === 'konbini') {
      setPaymentMethod('bank_transfer')
    }
  }, [isInternational, paymentMethod])

  
  // Fetch shipping rates
  useEffect(() => {
    if (!isMounted) return
    shippingApi.getRates().then(res => {
      setShippingRates(res.data)
    })
    paymentsApi.getStripeConfig().then(res => {
      setStripeEnabled(Boolean(res.data?.enabled))
    }).catch(() => setStripeEnabled(false))
  }, [isMounted])

  // Calculate allowed shipping methods intersection
  const allowedMethodCodes = (() => {
    if (!items.length) return null
    let intersection: Set<string> | null = null
    
    for (const item of items) {
      if (item.card.allowed_shipping_methods) {
        try {
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
    const isAlwaysShown = rate.method_code === 'takkyubin_compact' || rate.method_code === 'click_post'
    if (!isAlwaysShown && !rate.is_individual_available) return false
    if (isInternational) return rate.is_international_available
    if (!isInternational && rate.method_code === 'international') return false
    if (allowedMethodCodes === null) return true
    return allowedMethodCodes.includes(rate.method_code)
  })

  // Auto-select first available shipping method
  useEffect(() => {
    if (availableRates.length > 0) {
      const isCurrentAvailable = availableRates.some(r => r.method_code === shippingMethod)
      if (!isCurrentAvailable) {
        const preferred = availableRates.find(r => r.is_recommended) || availableRates.find(r => r.method_code === 'takkyubin_compact')
        setShippingMethod(preferred ? preferred.method_code : availableRates[0].method_code)
      }
    }
  }, [availableRates, shippingMethod])

  // Fetch dynamic shipping fee when method or destination changes
  useEffect(() => {
    if (!shippingMethod) {
      setDynamicShippingFee(null)
      return
    }

    shippingApi.calculateRate({
      method: shippingMethod,
      prefecture: debouncedAddress.region,
      country: debouncedAddress.country
    }).then(res => {
      setDynamicShippingFee(res.data.fee_jpy)
    }).catch(() => {
      const selectedRate = shippingRates.find(r => r.method_code === shippingMethod)
      setDynamicShippingFee(selectedRate?.fee_jpy || 0)
    })
  }, [shippingMethod, debouncedAddress, shippingRates])

  const selectedRate = shippingRates.find(r => r.method_code === shippingMethod)
  const shippingFee = dynamicShippingFee ?? (selectedRate?.fee_jpy || 0)
  const finalTotal = total + shippingFee

  const needsCompensationAgreement = selectedRate && !selectedRate.has_insurance

  // Pre-fill address if available
  useEffect(() => {
    if (user) {
      if (user.postal_code) setPostalCode(user.postal_code)
      if (user.country) setCountry(user.country === 'Japan' ? 'JP' : (user.country || 'JP'))
      if (user.region) setRegion(user.region)
      if (user.city) setCity(user.city)
      if (user.address_line1) setAddressLine1(user.address_line1)
      if (user.address_line2) setAddressLine2(user.address_line2)
      if (user.name) setFullName(user.name)
    }
  }, [user])

  useEffect(() => {
    if (!isMounted || !isReady) return
    if (!isLoggedIn) {
      router.push('/sign-in')
      return
    }
    void requireAuth().then((token) => {
      if (token) {
        fetchMe()
        fetchCart()
      }
    })
  }, [isMounted, isReady, isLoggedIn, router, fetchCart, fetchMe, requireAuth])

  useEffect(() => {
    if (!isMounted || !isReady || !isLoggedIn) return
    if (items.length === 0) {
      router.push('/cart')
    }
  }, [items, isMounted, isReady, isLoggedIn, router])

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

    if (!isInternational && needsCompensationAgreement && !agreedToNoCompensation) {
      toast({ title: t('エラー', lang), description: t('配送会社の補償規定および免責事項に同意します', lang), variant: 'destructive' })
      return
    }

    if (!agreedToTerms) {
      toast({ title: t('エラー', lang), description: t('利用規約およびプライバシーポリシーに同意します', lang), variant: 'destructive' })
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
      const token = await requireAuth()
      if (!token) {
        const clerkToken = await import('@/lib/clerk-token').then((m) => m.getClerkSessionToken())
        if (!clerkToken) {
          toast({
            title: t('エラー', lang),
            description:
              lang === 'ja'
                ? 'ログインセッションの確認に失敗しました。一度ログアウトして再ログインしてください。'
                : 'Failed to verify your login session. Please sign out and sign in again.',
            variant: 'destructive',
          })
          return
        }
      }

      const currentCountryObj = COUNTRIES.find(c => c.code === country)
      const currentCountryName = currentCountryObj ? (lang === 'ja' ? currentCountryObj.ja : currentCountryObj.en) : country
      const shippingAddress = country === 'JP'
        ? `〒${postalCode} ${region}${city}${addressLine1} ${addressLine2}`
        : `${fullName}, ${addressLine1}, ${addressLine2 ? addressLine2 + ', ' : ''}${city}, ${region} ${postalCode}, ${currentCountryName}`

      if (saveAddress) {
        await authApi.updateProfile({ 
          name: fullName || user?.name,
          postal_code: postalCode,
          country: currentCountryName,
          region: region,
          city: city,
          address_line1: addressLine1,
          address_line2: addressLine2,
          phone_number: user?.phone_number || ''
        })
        fetchMe()
      }

      if (paymentMethod === 'credit_card' || paymentMethod === 'konbini') {
        if (!stripeEnabled) {
          toast({
            title: t('エラー', lang),
            description: t('Stripe決済は現在利用できません', lang),
            variant: 'destructive',
          })
          return
        }

        if (paymentMethod === 'konbini' && isInternational) {
          toast({
            title: t('エラー', lang),
            description: t('コンビニ決済は日本国内のみ利用できます', lang),
            variant: 'destructive',
          })
          return
        }

        const stripeRes = await paymentsApi.createStripeCheckout({
          postal_code: postalCode,
          country: currentCountryName,
          region: region,
          city: city,
          address_line1: addressLine1,
          address_line2: addressLine2,
          shipping_address: shippingAddress,
          shipping_method: shippingMethod,
          locale: lang,
          checkout_type: paymentMethod === 'konbini' ? 'konbini' : 'card',
        })

        window.location.href = stripeRes.data.checkout_url
        return
      }

      const res = await ordersApi.create({
        postal_code: postalCode,
        country: currentCountryName,
        region: region,
        city: city,
        address_line1: addressLine1,
        address_line2: addressLine2,
        shipping_address: shippingAddress,
        shipping_method: shippingMethod,
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

  if (!isMounted || !isReady || !isLoggedIn || items.length === 0) return null

  return (
    <div className="min-h-screen bg-white" key={lang}>
      <div className="container py-8 max-w-2xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-6 text-center">{t('注文確認', lang)}</h1>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* 1. 配送先 */}
          <section className="bg-gray-50 rounded-lg border border-gray-200 p-5 space-y-4">
            <h2 className="text-gray-900 font-semibold flex items-center gap-2">
              <span className="flex items-center justify-center w-6 h-6 rounded-full bg-yellow-400 text-gray-950 text-xs font-bold">1</span>
              {t('配送先', lang)}
            </h2>
            <div className="grid grid-cols-1 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="country" className="text-gray-600 text-sm">{t('国', lang)}</Label>
                    <select
                      id="country"
                      value={country}
                      onChange={(e) => setCountry(e.target.value)}
                      required
                      className="w-full h-10 px-3 bg-white border border-gray-300 rounded-md text-gray-900 focus:ring-yellow-400/50"
                    >
                      {COUNTRIES.map(c => (
                        <option key={c.code} value={c.code}>{lang === 'ja' ? c.ja : c.en}</option>
                      ))}
                    </select>
                  </div>

                {isInternational ? (
                  <>
                    <div className="space-y-2">
                      <Label htmlFor="fullName" className="text-gray-600 text-sm">{t('氏名', lang)}</Label>
                      <Input
                        id="fullName"
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        placeholder="John Doe"
                        required
                        className="bg-white border-gray-300 text-gray-900 focus:ring-yellow-400/50"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="addressLine1" className="text-gray-600 text-sm">{t('住所番地', lang)}</Label>
                      <Input
                        id="addressLine1"
                        value={addressLine1}
                        onChange={(e) => setAddressLine1(e.target.value)}
                        placeholder="123 Main St"
                        required
                        className="bg-white border-gray-300 text-gray-900 focus:ring-yellow-400/50"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="addressLine2" className="text-gray-600 text-sm">{t('建物名・部屋番号（任意）', lang)}</Label>
                      <Input
                        id="addressLine2"
                        value={addressLine2}
                        onChange={(e) => setAddressLine2(e.target.value)}
                        placeholder="Apt 101"
                        className="bg-white border-gray-300 text-gray-900 focus:ring-yellow-400/50"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="city" className="text-gray-600 text-sm">{t('市区町村', lang)}</Label>
                        <Input
                          id="city"
                          value={city}
                          onChange={(e) => setCity(e.target.value)}
                          placeholder="New York"
                          required
                          className="bg-white border-gray-300 text-gray-900 focus:ring-yellow-400/50"
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="region" className="text-gray-600 text-sm">{t('都道府県', lang)}</Label>
                        <Input
                          id="region"
                          value={region}
                          onChange={(e) => setRegion(e.target.value)}
                          placeholder="NY"
                          required
                          className="bg-white border-gray-300 text-gray-900 focus:ring-yellow-400/50"
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="postalCode" className="text-gray-600 text-sm">{t('郵便番号', lang)}</Label>
                      <Input
                        id="postalCode"
                        value={postalCode}
                        onChange={(e) => setPostalCode(e.target.value)}
                        placeholder="10001"
                        required
                        className="bg-white border-gray-300 text-gray-900 focus:ring-yellow-400/50"
                      />
                    </div>
                  </>
                ) : (
                  <>
                    <div className="space-y-2">
                      <Label htmlFor="postalCode" className="text-gray-600 text-sm">{t('郵便番号', lang)}</Label>
                      <div className="relative">
                        <Input
                          id="postalCode"
                          value={postalCode}
                          onChange={(e) => setPostalCode(e.target.value)}
                          placeholder="000-0000"
                          required
                          className="bg-white border-gray-300 text-gray-900 focus:ring-yellow-400/50 pr-10"
                        />
                        {isFetchingAddress && (
                          <div className="absolute right-3 top-1/2 -translate-y-1/2">
                            <RefreshCw className="h-4 w-4 text-yellow-400 animate-spin" />
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="region" className="text-gray-600 text-sm">{t('都道府県', lang)}</Label>
                      <select
                        id="region"
                        value={region}
                        onChange={(e) => setRegion(e.target.value)}
                        required
                        className="w-full h-10 px-3 bg-white border border-gray-300 rounded-md text-gray-900 focus:ring-yellow-400/50"
                      >
                        <option value="">{t('都道府県を入力してください', lang)}</option>
                        {PREFECTURES.map(p => (
                          <option key={p} value={p}>{t(p, lang)}</option>
                        ))}
                      </select>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="city" className="text-gray-600 text-sm">{t('市区町村', lang)}</Label>
                      <Input
                        id="city"
                        value={city}
                        onChange={(e) => setCity(e.target.value)}
                        placeholder="渋谷区"
                        required
                        className="bg-white border-gray-300 text-gray-900 focus:ring-yellow-400/50"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="addressLine1" className="text-gray-600 text-sm">{t('住所番地', lang)}</Label>
                      <Input
                        id="addressLine1"
                        value={addressLine1}
                        onChange={(e) => setAddressLine1(e.target.value)}
                        placeholder="神南1-1-1"
                        required
                        className="bg-white border-gray-300 text-gray-900 focus:ring-yellow-400/50"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="addressLine2" className="text-gray-600 text-sm">{t('建物名・部屋番号（任意）', lang)}</Label>
                      <Input
                        id="addressLine2"
                        value={addressLine2}
                        onChange={(e) => setAddressLine2(e.target.value)}
                        placeholder="〇〇ビル 101"
                        className="bg-white border-gray-300 text-gray-900 focus:ring-yellow-400/50"
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
                    className="w-4 h-4 rounded border-gray-300 bg-white text-yellow-400 focus:ring-yellow-400"
                  />
                  <Label htmlFor="saveAddress" className="text-gray-400 text-xs cursor-pointer">
                    {t('この住所を保存して次回から自動入力する', lang)}
                  </Label>
                </div>
            </div>
          </section>

          {/* 2. 発送方法 */}
          <section className="bg-gray-50 rounded-lg border border-gray-200 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-gray-900 font-semibold flex items-center gap-2">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-yellow-400 text-gray-950 text-xs font-bold">2</span>
                {t('発送方法', lang)}
              </h2>
              <Link href="/shipping-policy" className="text-xs text-yellow-400 hover:underline">
                {t('補償について詳しく', lang)}
              </Link>
            </div>

            <div className="space-y-2">
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
                  <div className="grid gap-3">
                    {availableRates.map(rate => (
                      <label 
                        key={rate.method_code}
                        className={`relative flex flex-col gap-1 p-4 rounded-xl border cursor-pointer transition-all ${shippingMethod === rate.method_code ? 'bg-yellow-400/10 border-yellow-400 shadow-[0_0_15px_rgba(250,204,21,0.1)]' : 'bg-gray-50 border-gray-200 hover:border-gray-300'}`}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-3">
                            <input
                              type="radio"
                              name="shipping"
                              value={rate.method_code}
                              checked={shippingMethod === rate.method_code}
                              onChange={() => setShippingMethod(rate.method_code)}
                              className="w-4 h-4 accent-yellow-400"
                            />
                            <div>
                              <p className="text-gray-900 text-sm font-bold flex items-center gap-2">
                                {lang === 'ja' ? rate.name_ja : rate.name_en}
                                {rate.is_recommended && (
                                  <Badge className="bg-yellow-400 text-gray-950 hover:bg-yellow-400 text-[9px] h-4 px-1 font-bold">
                                    {t('推奨', lang)}
                                  </Badge>
                                )}
                              </p>
                            </div>
                          </div>
                          <p className="text-yellow-400 font-bold text-sm">
                            {formatPrice(rate.fee_jpy || 0)}
                          </p>
                        </div>

                        <div className="ml-7 grid grid-cols-2 gap-2 mt-2">
                          <div className="flex items-center gap-1.5 text-[11px] text-gray-400">
                            <Truck className="h-3 w-3 text-gray-500" />
                            <span>{t('追跡', lang)}: {rate.has_tracking ? t('あり', lang) : t('なし', lang)}</span>
                          </div>
                          <div className="flex items-center gap-1.5 text-[11px] text-gray-400">
                            <ShieldCheck className="h-3 w-3 text-gray-500" />
                            <span>
                              {t('補償', lang)}: {rate.has_insurance ? (rate.insurance_max_amount ? `Max ${formatPrice(rate.insurance_max_amount)}` : t('あり', lang)) : t('なし', lang)}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5 text-[11px] text-gray-400">
                            <Info className="h-3 w-3 text-gray-500" />
                            <span>
                              {t('到着目安', lang)}: {rate.estimated_delivery_min_days}〜{rate.estimated_delivery_max_days}{t('日', lang)}
                            </span>
                          </div>
                          {rate.insurance_url && (
                            <a 
                              href={rate.insurance_url} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="flex items-center gap-1 text-[11px] text-yellow-400/70 hover:text-yellow-400 transition-colors"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <ExternalLink className="h-3 w-3" />
                              {t('補償詳細', lang)}
                            </a>
                          )}
                        </div>

                        {shippingMethod === rate.method_code && (
                          <div className="absolute top-3 right-3">
                            <div className="bg-yellow-400 rounded-full p-0.5">
                              <Check className="h-3 w-3 text-gray-950 font-bold" />
                            </div>
                          </div>
                        )}
                      </label>
                    ))}
                  </div>
                )}
            </div>
          </section>

          {/* 3. 注文内容確認 */}
          <section className="bg-gray-50 rounded-lg border border-gray-200 p-5 space-y-4">
            <h2 className="text-gray-900 font-semibold flex items-center gap-2">
              <span className="flex items-center justify-center w-6 h-6 rounded-full bg-yellow-400 text-gray-950 text-xs font-bold">3</span>
              {t('注文内容確認', lang)}
            </h2>
            <div className="space-y-3">
              {items.map((item) => (
                <CheckoutItemRow key={item.id} item={item} formatPrice={formatPrice} lang={lang} />
              ))}
              <div className="border-t border-gray-200 pt-3 space-y-1 text-sm">
                <div className="flex justify-between text-gray-400">
                  <span>{t('小計', lang)}</span>
                  <span>{formatPrice(total)}</span>
                </div>
                <div className="flex justify-between text-gray-400">
                  <span>{t('送料', lang)}</span>
                  <span>{formatPrice(shippingFee)}</span>
                </div>
              </div>
              <div className="border-t border-gray-200 pt-3 flex justify-between font-bold">
                <span className="text-gray-400">{t('合計', lang)}</span>
                <span className="text-yellow-400 text-lg">{formatPrice(finalTotal)}</span>
              </div>
            </div>
          </section>

          {/* 4. 支払い方法 */}
          <section className="bg-gray-50 rounded-lg border border-gray-200 p-5 space-y-4">
            <h2 className="text-gray-900 font-semibold flex items-center gap-2">
              <span className="flex items-center justify-center w-6 h-6 rounded-full bg-yellow-400 text-gray-950 text-xs font-bold">4</span>
              {t('支払い方法', lang)}
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {[
                { value: 'credit_card', label: t('クレジットカード（Stripe）', lang), disabled: !stripeEnabled },
                { value: 'konbini', label: t('コンビニ決済（Stripe）', lang), disabled: !stripeEnabled || isInternational },
                { value: 'bank_transfer', label: t('銀行振込', lang), disabled: false },
                { value: 'cod', label: t('代金引換', lang), disabled: false },
              ].map((method) => (
                <label key={method.value} className={`flex items-center gap-2 p-3 rounded-lg border transition-colors ${method.disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'} ${paymentMethod === method.value ? 'bg-yellow-400/5 border-yellow-400/50' : 'bg-gray-50 border-gray-100'}`}>
                  <input
                    type="radio"
                    name="payment"
                    value={method.value}
                    checked={paymentMethod === method.value}
                    disabled={method.disabled}
                    onChange={() => setPaymentMethod(method.value)}
                    className="accent-yellow-400"
                  />
                  <span className="text-gray-600 text-xs">{method.label}</span>
                </label>
              ))}
            </div>
            {paymentMethod === 'credit_card' && (
              <p className="text-xs text-gray-500">
                {t('Stripeの安全な決済ページに移動してカード情報を入力します', lang)}
              </p>
            )}
            {paymentMethod === 'konbini' && (
              <p className="text-xs text-gray-500">
                {t('Stripeのページで支払番号を発行します。3日以内にコンビニでお支払いください', lang)}
              </p>
            )}
          </section>

          {/* 5. 同意事項 */}
          <section className="bg-gray-50 rounded-lg border border-gray-200 p-5 space-y-4">
            <h2 className="text-gray-900 font-semibold flex items-center gap-2">
              <span className="flex items-center justify-center w-6 h-6 rounded-full bg-yellow-400 text-gray-950 text-xs font-bold">5</span>
              {t('同意事項', lang)}
            </h2>
            
            <div className="space-y-3">
              <div className="p-4 bg-gray-50 border border-gray-100 rounded-lg space-y-3">
                <label className="flex items-center gap-3 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={agreedToTerms}
                    onChange={(e) => setAgreedToTerms(e.target.checked)}
                    className="w-4 h-4 rounded border-gray-300 bg-white text-yellow-400 focus:ring-yellow-400"
                  />
                  <span className="text-sm text-gray-600 group-hover:text-gray-900 transition-colors">
                    {t('利用規約およびプライバシーポリシーに同意します', lang)}
                  </span>
                </label>
              </div>

              {needsCompensationAgreement && (
                <div className="p-4 bg-yellow-400/5 border border-yellow-400/20 rounded-lg space-y-3">
                  <p className="text-xs text-gray-600 leading-relaxed">
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
                      className="w-4 h-4 rounded border-gray-300 bg-white text-yellow-400 focus:ring-yellow-400"
                    />
                    <span className="text-sm text-yellow-400 font-bold group-hover:text-yellow-300 transition-colors">
                      {t('配送会社の補償規定および免責事項に同意します', lang)}
                    </span>
                  </label>
                </div>
              )}
            </div>
          </section>

          {/* 注文確定ボタン */}
          <div className="pt-4">
            <Button
              type="submit"
              disabled={isSubmitting || (!isInternational && availableRates.length === 0)}
              className="w-full h-14 bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-black text-lg shadow-xl shadow-yellow-400/10"
            >
              {isSubmitting
                ? t('注文処理中...', lang)
                : paymentMethod === 'credit_card'
                  ? t('Stripeで支払う', lang)
                  : paymentMethod === 'konbini'
                    ? t('コンビニ決済へ進む', lang)
                    : t('注文を確定する', lang)}
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
  const translatedCardName = useTranslation(item.card?.name)
  const cardName = (lang === 'en' && item.card?.name_en) ? item.card.name_en : translatedCardName
  return (
    <div className="flex gap-3 items-center">
      <div className="relative w-12 h-16 flex-shrink-0 rounded overflow-hidden bg-white">
        {item.card?.image_url ? (
          <Image src={item.card.image_url} alt={cardName} fill className="object-cover" />
        ) : (
          <div className="flex items-center justify-center h-full text-xl">🃏</div>
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-gray-900 text-sm font-medium truncate">{cardName || t('不明なカード', lang)}</p>
        <p className="text-gray-500 text-xs">{item.card?.rarity} × {item.quantity}</p>
      </div>
      <p className="text-yellow-400 font-bold text-sm">
        {formatPrice((item.card?.price || 0) * item.quantity)}
      </p>
    </div>
  )
}
