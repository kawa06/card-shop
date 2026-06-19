'use client'

import { useState, useEffect } from 'react'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/auth'
import { useCartStore } from '@/store/cart'
import { ordersApi, authApi } from '@/lib/api'
import { toast } from '@/lib/use-toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function CheckoutPage() {
  const router = useRouter()
  const { isAuthenticated, user, isLoading: isAuthLoading, fetchMe } = useAuthStore()
  const { items, total, fetchCart, clearCart } = useCartStore()
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const [postalCode, setPostalCode] = useState('')
  const [region, setRegion] = useState('')
  const [city, setCity] = useState('')
  const [addressLine1, setAddressLine1] = useState('')
  const [addressLine2, setAddressLine2] = useState('')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [paymentMethod, setPaymentMethod] = useState('credit_card')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [saveAddress, setSaveAddress] = useState(true)

  // Pre-fill address if available
  useEffect(() => {
    if (user) {
      if (user.postal_code) setPostalCode(user.postal_code)
      if (user.region) setRegion(user.region)
      if (user.city) setCity(user.city)
      if (user.address_line1) setAddressLine1(user.address_line1)
      if (user.address_line2) setAddressLine2(user.address_line2)
      if (user.phone_number) setPhoneNumber(user.phone_number)
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
    if (!postalCode.trim()) {
      toast({ title: 'エラー', description: '郵便番号を入力してください', variant: 'destructive' })
      return
    }
    if (!region.trim()) {
      toast({ title: 'エラー', description: '都道府県を入力してください', variant: 'destructive' })
      return
    }
    if (!city.trim()) {
      toast({ title: 'エラー', description: '市区町村を入力してください', variant: 'destructive' })
      return
    }
    if (!addressLine1.trim()) {
      toast({ title: 'エラー', description: '住所番地を入力してください', variant: 'destructive' })
      return
    }

    if (!phoneNumber.trim()) {
      toast({ title: 'エラー', description: '電話番号を入力してください', variant: 'destructive' })
      return
    }

    setIsSubmitting(true)
    try {
      // 1. Update user profile if saveAddress is checked
      if (saveAddress) {
        await authApi.updateProfile({ 
          postal_code: postalCode,
          country: 'Japan',
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
        country: 'Japan',
        region: region,
        city: city,
        address_line1: addressLine1,
        address_line2: addressLine2,
        shipping_address: `〒${postalCode} ${region}${city}${addressLine1} ${addressLine2} (Tel: ${phoneNumber})`,
        payment_method: paymentMethod,
      })
      
      clearCart()
      toast({ title: '注文が完了しました！', description: `注文番号: #${res.data.id}` })
      router.push('/orders')
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        '注文に失敗しました。もう一度お試しください。'
      toast({ title: 'エラー', description: message, variant: 'destructive' })
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isMounted || isAuthLoading || !isAuthenticated || items.length === 0) return null

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="container py-8 max-w-4xl">
        <h1 className="text-2xl font-bold text-white mb-6">注文確認</h1>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Order Items */}
          <div>
            <h2 className="text-white font-semibold mb-3">注文内容</h2>
            <div className="bg-gray-900 rounded-lg border border-white/10 p-4 space-y-3">
              {items.map((item) => (
                <div key={item.id} className="flex gap-3 items-center">
                  <div className="relative w-12 h-16 flex-shrink-0 rounded overflow-hidden bg-gray-800">
                    {item.card?.image_url ? (
                      <Image src={item.card.image_url} alt={item.card.name} fill className="object-cover" />
                    ) : (
                      <div className="flex items-center justify-center h-full text-xl">🃏</div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-white text-sm font-medium truncate">{item.card?.name || '不明なカード'}</p>
                    <p className="text-gray-500 text-xs">{item.card?.rarity} × {item.quantity}</p>
                  </div>
                  <p className="text-yellow-400 font-bold text-sm">
                    ¥{((item.card?.price || 0) * item.quantity).toLocaleString()}
                  </p>
                </div>
              ))}
              <div className="border-t border-white/10 pt-3 flex justify-between font-bold">
                <span className="text-gray-400">合計</span>
                <span className="text-yellow-400 text-lg">¥{total.toLocaleString()}</span>
              </div>
            </div>
          </div>

          {/* Checkout Form */}
          <div>
            <h2 className="text-white font-semibold mb-3">配送・支払い情報</h2>
            <form onSubmit={handleSubmit} className="bg-gray-900 rounded-lg border border-white/10 p-5 space-y-5">
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="postalCode" className="text-gray-300 text-sm">郵便番号</Label>
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
                  <Label htmlFor="region" className="text-gray-300 text-sm">都道府県</Label>
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
                  <Label htmlFor="city" className="text-gray-300 text-sm">市区町村</Label>
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
                  <Label htmlFor="addressLine1" className="text-gray-300 text-sm">住所番地</Label>
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
                  <Label htmlFor="addressLine2" className="text-gray-300 text-sm">建物名・部屋番号（任意）</Label>
                  <Input
                    id="addressLine2"
                    value={addressLine2}
                    onChange={(e) => setAddressLine2(e.target.value)}
                    placeholder="〇〇ビル 101"
                    className="bg-gray-800 border-gray-700 text-white focus:ring-yellow-400/50"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="phoneNumber" className="text-gray-300 text-sm">電話番号</Label>
                  <Input
                    id="phoneNumber"
                    type="tel"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    placeholder="090-0000-0000"
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
                    この住所を保存して次回から自動入力する
                  </Label>
                </div>
              </div>

              <div className="space-y-2 border-t border-white/5 pt-4">
                <Label className="text-gray-300 text-sm">支払い方法</Label>
                <div className="space-y-2">
                  {[
                    { value: 'credit_card', label: 'クレジットカード（後日実装）' },
                    { value: 'bank_transfer', label: '銀行振込' },
                    { value: 'cod', label: '代金引換' },
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
                {isSubmitting ? '注文処理中...' : '注文を確定する'}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
