'use client'

import { useState, useEffect } from 'react'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/auth'
import { useCartStore } from '@/store/cart'
import { ordersApi, authApi } from '@/lib/api'
import { toast } from '@/lib/use-toast'
import { formatPrice, usePrice } from '@/lib/format'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { useTranslation } from '@/hooks/useTranslation'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

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
  const [paymentMethod, setPaymentMethod] = useState('credit_card')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [saveAddress, setSaveAddress] = useState(true)

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
      toast({ title: t('エラー', lang), description: lang === 'ja' ? '氏名を入力してください' : 'Please enter full name', variant: 'destructive' })
      return
    }

    if (!phoneNumber.trim()) {
      toast({ title: t('エラー', lang), description: t('電話番号を入力してください', lang), variant: 'destructive' })
      return
    }

    setIsSubmitting(true)
    try {
      const currentCountry = lang === 'ja' ? 'Japan' : country
      const shippingAddress = lang === 'ja'
        ? `〒${postalCode} ${region}${city}${addressLine1} ${addressLine2} (Tel: ${phoneNumber})`
        : `${fullName}, ${addressLine1}, ${addressLine2 ? addressLine2 + ', ' : ''}${city}, ${region} ${postalCode}, ${currentCountry} (Tel: ${phoneNumber})`

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
          phone_number: phoneNumber
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
      <div className="container py-8 max-w-4xl">
        <h1 className="text-2xl font-bold text-white mb-6">{t('注文確認', lang)}</h1>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Order Items */}
          <div>
            <h2 className="text-white font-semibold mb-3">{t('注文内容', lang)}</h2>
            <div className="bg-gray-900 rounded-lg border border-white/10 p-4 space-y-3">
              {items.map((item) => (
                <CheckoutItemRow key={item.id} item={item} formatPrice={formatPrice} lang={lang} />
              ))}
              <div className="border-t border-white/10 pt-3 flex justify-between font-bold">
                <span className="text-gray-400">{t('合計', lang)}</span>
                <span className="text-yellow-400 text-lg">{formatPrice(total)}</span>
              </div>
            </div>
          </div>

          {/* Checkout Form */}
          <div>
            <h2 className="text-white font-semibold mb-3">{t('配送・支払い情報', lang)}</h2>
            <form onSubmit={handleSubmit} className="bg-gray-900 rounded-lg border border-white/10 p-5 space-y-5">
              <div className="space-y-4">
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
                      <Input
                        id="region"
                        value={region}
                        onChange={(e) => setRegion(e.target.value)}
                        placeholder="東京都"
                        required
                        className="bg-gray-800 border-gray-700 text-white focus:ring-yellow-400/50"
                      />
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

                <div className="space-y-2">
                  <Label htmlFor="phoneNumber" className="text-gray-300 text-sm">{t('電話番号', lang)}</Label>
                  <Input
                    id="phoneNumber"
                    type="tel"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    placeholder={lang === 'en' ? "+1-000-000-0000" : "090-0000-0000"}
                    required
                    className="bg-gray-800 border-gray-700 text-white focus:ring-yellow-400/50"
                  />
                </div>

                <div className="flex items-center gap-2">
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

              <div className="space-y-2 border-t border-white/5 pt-4">
                <Label className="text-gray-300 text-sm">{t('支払い方法', lang)}</Label>
                <div className="space-y-2">
                  {[
                    { value: 'credit_card', label: t('クレジットカード（後日実装）', lang) },
                    { value: 'bank_transfer', label: t('銀行振込', lang) },
                    { value: 'cod', label: t('代金引換', lang) },
                  ].map((method) => (
                    <label key={method.value} className="flex items-center gap-3 cursor-pointer">
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

              <Button
                type="submit"
                disabled={isSubmitting}
                className="w-full h-11 bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold"
              >
                {isSubmitting ? t('注文処理中...', lang) : t('注文を確定する', lang)}
              </Button>
            </form>
          </div>
        </div>
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
