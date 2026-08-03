'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth, useUser } from '@clerk/nextjs'
import { User, Package, Heart, MapPin, Trash2, AlertTriangle, Key, ShieldCheck, Mail, CheckCircle2, Phone, Smartphone, MessageSquare, Bell, UserRound } from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { ordersApi, authApi, favoritesApi, inquiriesApi, announcementsApi } from '@/lib/api'
import { Order, User as UserType } from '@/lib/types'
import { usePrice } from '@/lib/format'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'
import { MypageSecurityPanel } from '@/components/mypage/MypageSecurityPanel'

import { isAdminEmail } from '@/lib/auth/admin'

function userFromClerk(clerkUser: NonNullable<ReturnType<typeof useUser>['user']>): UserType {
  const email =
    clerkUser.emailAddresses.find((e) => e.id === clerkUser.primaryEmailAddressId)?.emailAddress ||
    clerkUser.emailAddresses[0]?.emailAddress ||
    ''

  return {
    id: 0,
    email,
    name: clerkUser.firstName || clerkUser.username || email.split('@')[0] || 'User',
    is_admin: isAdminEmail(email),
    is_verified: true,
    postal_code: null,
    country: null,
    region: null,
    city: null,
    address_line1: null,
    address_line2: null,
    address: null,
    phone_number: null,
    phone_verified: false,
    created_at: '',
  }
}

export default function MypagePage() {
  const router = useRouter()
  const { isSignedIn, isLoaded } = useAuth()
  const { user: clerkUser } = useUser()
  const {
    isAuthenticated,
    user,
    token,
    logout,
    fetchMe,
    syncBackend,
    hasHydrated,
    setHasHydrated,
    authProvider,
  } = useAuthStore()
  const { formatPrice } = usePrice()
  const { lang } = useLangStore()
  const [orders, setOrders] = useState<Order[]>([])
  const [favoriteCount, setFavoriteCount] = useState<number | null>(null)
  const [inquiryUnreadCount, setInquiryUnreadCount] = useState<number | null>(null)
  const [announcementUnreadCount, setAnnouncementUnreadCount] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isDeleting, setIsDeleting] = useState(false)
  
  // Client-side hydration safety
  const [isMounted, setIsMounted] = useState(false)

  // Password change state
  const [showPasswordForm, setShowPasswordForm] = useState(false)
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [isUpdatingPassword, setIsUpdatingPassword] = useState(false)

  // Email verification state
  const [isRequestingVerify, setIsRequestingVerify] = useState(false)

  // Phone verification state
  const [phone, setPhone] = useState('')
  const [otpCode, setOtpCode] = useState('')
  const [isSendingOtp, setIsSendingOtp] = useState(false)
  const [isVerifyingOtp, setIsVerifyingOtp] = useState(false)
  const [showPhoneVerify, setShowPhoneVerify] = useState(false)
  const [isDebugMode, setIsDebugMode] = useState(false)

  const normalizePhone = (raw: string) => {
    const cleaned = raw.trim().replace(/[\s-]/g, '')
    if (cleaned.startsWith('0') && cleaned.length > 0) {
      return '+81' + cleaned.slice(1)
    }
    return cleaned
  }

  useEffect(() => {
    if (user?.phone_number) {
      setPhone(user.phone_number)
    }
  }, [user])

  useEffect(() => {
    if (hasHydrated) return
    const initAuth = async () => {
      await useAuthStore.persist.rehydrate()
      setHasHydrated(true)
    }
    initAuth()
  }, [hasHydrated, setHasHydrated])

  useEffect(() => {
    setIsMounted(true)
  }, [])

  useEffect(() => {
    if (!isMounted || !isLoaded || !hasHydrated) return

    let cancelled = false

    const initPage = async () => {
      if (isSignedIn && !isAuthenticated) {
        try {
          await syncBackend()
        } catch {
          // バックエンド未接続時も Clerk 情報でページを表示
        }
      }

      if (!isSignedIn && !isAuthenticated) {
        router.push('/sign-in')
        return
      }

      const { token, isAuthenticated: authed } = useAuthStore.getState()
      if (authed && token) {
        fetchMe()
        ordersApi.getAll().then((res) => {
          if (!cancelled) setOrders((res.data || []).slice(0, 3))
        }).catch(() => {})
        favoritesApi.getIds().then((res) => {
          if (!cancelled) setFavoriteCount((res.data || []).length)
        }).catch(() => {
          if (!cancelled) setFavoriteCount(0)
        })
        inquiriesApi.getUnreadCount().then((res) => {
          if (!cancelled) setInquiryUnreadCount(res.data?.count ?? 0)
        }).catch(() => {
          if (!cancelled) setInquiryUnreadCount(0)
        })
        announcementsApi.getUnreadCount().then((res) => {
          if (!cancelled) setAnnouncementUnreadCount(res.data?.count ?? 0)
        }).catch(() => {
          if (!cancelled) setAnnouncementUnreadCount(0)
        }).finally(() => {
          if (!cancelled) setIsLoading(false)
        })
      } else if (!cancelled) {
        setIsLoading(false)
      }
    }

    initPage()
    return () => { cancelled = true }
  }, [isMounted, isLoaded, hasHydrated, isSignedIn, isAuthenticated, router, fetchMe, syncBackend])

  const handleDeleteAccount = async () => {
    const confirmed = confirm(lang === 'ja' ? '本当にアカウントを削除しますか？この操作は取り消せません。' : 'Are you sure you want to delete your account? This action cannot be undone.')
    if (!confirmed) return

    setIsDeleting(true)
    try {
      await authApi.deleteAccount()
      toast({ title: t('アカウントを削除しました', lang), description: lang === 'ja' ? 'ご利用ありがとうございました。' : 'Thank you for using our service.' })
      logout()
      router.push('/')
    } catch {
      toast({ title: t('エラー', lang), description: lang === 'ja' ? 'アカウントの削除に失敗しました。' : 'Failed to delete account.', variant: 'destructive' })
    } finally {
      setIsDeleting(false)
    }
  }

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    if (newPassword.length < 8) {
      toast({ title: t('エラー', lang), description: lang === 'ja' ? '新しいパスワードは8文字以上で入力してください' : 'New password must be at least 8 characters long', variant: 'destructive' })
      return
    }

    setIsUpdatingPassword(true)
    try {
      await authApi.changePassword({ old_password: oldPassword, new_password: newPassword })
      toast({ title: lang === 'ja' ? '完了' : 'Success', description: lang === 'ja' ? 'パスワードを更新しました。' : 'Password updated successfully.' })
      setShowPasswordForm(false)
      setOldPassword('')
      setNewPassword('')
    } catch (err: any) {
      const msg = err.response?.data?.detail || (lang === 'ja' ? 'パスワードの変更に失敗しました。' : 'Failed to change password.')
      toast({ title: t('エラー', lang), description: msg, variant: 'destructive' })
    } finally {
      setIsUpdatingPassword(false)
    }
  }

  const handleRequestVerification = async () => {
    setIsRequestingVerify(true)
    try {
      const res = await authApi.requestVerification()
      toast({
        title: lang === 'ja' ? 'リクエスト送信' : 'Request Sent',
        description: res.data.message,
      })
    } catch {
      toast({ title: t('エラー', lang), description: lang === 'ja' ? '認証リクエストに失敗しました。' : 'Failed to request verification.', variant: 'destructive' })
    } finally {
      setIsRequestingVerify(false)
    }
  }

  const handleSendOtp = async () => {
    if (!phone.trim()) {
      toast({ title: t('エラー', lang), description: t('電話番号を入力してください', lang), variant: 'destructive' })
      return
    }
    setIsSendingOtp(true)
    try {
      const normalizedPhone = normalizePhone(phone)
      const res = await authApi.sendPhoneOtp(normalizedPhone)
      setPhone(normalizedPhone)
      setIsDebugMode(res.data.debug || false)
      toast({
        title: lang === 'ja' ? '送信しました' : 'Sent',
        description: res.data.debug
          ? 'SMSをご確認ください（デモ環境: 認証コードは 000000）'
          : 'SMSをご確認ください / SMS sent, please check your phone'
      })
      setShowPhoneVerify(true)
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
      await authApi.verifyPhoneOtp(phone, otpCode)
      toast({ title: t('認証に成功しました', lang), description: t('電話番号の認証が完了しました', lang) })
      setShowPhoneVerify(false)
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

  const isClerkUser = authProvider === 'clerk' || (isSignedIn && !user)
  const displayUser = user ?? (isSignedIn && clerkUser ? userFromClerk(clerkUser) : null)

  if (!isMounted || !isLoaded || !hasHydrated) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-yellow-400 border-t-transparent" />
      </div>
    )
  }

  if (!isSignedIn && !isAuthenticated) return null

  if (!displayUser) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-yellow-400 border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-3xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">{t('マイページ', lang)}</h1>

        {/* Profile Card */}
        <div className="bg-gray-50 rounded-xl border border-gray-200 p-6 mb-6">
          <div className="flex flex-col sm:flex-row sm:items-center gap-6">
            <div className="w-20 h-20 rounded-full bg-yellow-400/10 border border-yellow-400/20 flex items-center justify-center flex-shrink-0">
              <User className="h-10 w-10 text-yellow-400" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-xl font-bold text-gray-900">{displayUser.name}</h2>
                {displayUser.is_admin && (
                  <span className="text-[10px] bg-yellow-400/20 text-yellow-400 px-2 py-0.5 rounded border border-yellow-400/20">
                    {t('管理者', lang)}
                  </span>
                )}
                {displayUser.is_verified ? (
                  <span className="flex items-center gap-1 text-[10px] bg-green-500/20 text-green-400 px-2 py-0.5 rounded border border-green-500/20">
                    <CheckCircle2 className="h-3 w-3" /> {t('認証済み', lang)}
                  </span>
                ) : !isClerkUser ? (
                  <span className="flex items-center gap-1 text-[10px] bg-gray-500/20 text-gray-400 px-2 py-0.5 rounded border border-gray-500/20">
                    {t('未認証', lang)}
                  </span>
                ) : null}
                {!isClerkUser && (
                  displayUser.phone_verified ? (
                    <span className="flex items-center gap-1 text-[10px] bg-green-500/20 text-green-400 px-2 py-0.5 rounded border border-green-500/20">
                      <Smartphone className="h-3 w-3" /> {t('電話番号認証', lang)}
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-[10px] bg-yellow-400/20 text-yellow-400 px-2 py-0.5 rounded border border-yellow-400/20">
                      <Smartphone className="h-3 w-3" /> {t('電話番号未認証', lang)}
                    </span>
                  )
                )}
              </div>
              <p className="text-gray-400 text-sm mt-1">{displayUser.email}</p>
              <p className="text-gray-500 text-xs mt-1">
                {displayUser.postal_code && `〒${displayUser.postal_code} `}
                {displayUser.region}{displayUser.city}{displayUser.address_line1} {displayUser.address_line2}
              </p>
              {displayUser.address && !displayUser.region && (
                <p className="text-gray-500 text-xs mt-1">{displayUser.address}</p>
              )}
              
              {!isClerkUser && (
                <div className="flex gap-4 mt-2">
                  {!displayUser.is_verified && (
                    <button
                      onClick={handleRequestVerification}
                      disabled={isRequestingVerify}
                      className="text-yellow-400 text-xs hover:underline disabled:opacity-50"
                    >
                      {isRequestingVerify ? t('処理中...', lang) : t('認証メールを再送する', lang)}
                    </button>
                  )}
                  {!displayUser.phone_verified && (
                    <button
                      onClick={() => setShowPhoneVerify(!showPhoneVerify)}
                      className="text-yellow-400 text-xs hover:underline"
                    >
                      {t('電話番号認証', lang)}
                    </button>
                  )}
                </div>
              )}
            </div>
            {!isClerkUser && (
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="border-gray-200 text-gray-600 hover:text-gray-900"
                  onClick={() => setShowPasswordForm(!showPasswordForm)}
                >
                  <Key className="h-4 w-4 mr-2" />
                  {t('パスワード変更', lang)}
                </Button>
              </div>
            )}
          </div>

          {/* Password Change Form */}
          {!isClerkUser && showPasswordForm && (
            <div className="mt-6 pt-6 border-t border-gray-100 animate-in slide-in-from-top-2">
              <form onSubmit={handleChangePassword} className="space-y-4 max-w-sm">
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">{t('現在のパスワード', lang)}</Label>
                  <Input 
                    type="password" 
                    value={oldPassword} 
                    onChange={e => setOldPassword(e.target.value)}
                    required
                    className="bg-white border-gray-300 text-gray-900 h-9"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">{t('新しいパスワード', lang)}</Label>
                  <Input 
                    type="password" 
                    value={newPassword} 
                    onChange={e => setNewPassword(e.target.value)}
                    required
                    minLength={8}
                    className="bg-white border-gray-300 text-gray-900 h-9"
                  />
                </div>
                <div className="flex gap-2">
                  <Button type="submit" size="sm" disabled={isUpdatingPassword} className="bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold">
                    {isUpdatingPassword ? t('更新中...', lang) : t('パスワードを更新', lang)}
                  </Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setShowPasswordForm(false)} className="text-gray-400">
                    {t('キャンセル', lang)}
                  </Button>
                </div>
              </form>
            </div>
          )}

          {/* Phone Verification Form */}
          {!isClerkUser && showPhoneVerify && !displayUser.phone_verified && (
            <div className="mt-6 pt-6 border-t border-gray-100 animate-in slide-in-from-top-2">
              <div className="max-w-sm space-y-4">
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">{t('電話番号', lang)} / Phone number</Label>
                  <div className="flex gap-2">
                    <Input 
                      type="tel" 
                      value={phone} 
                      onChange={e => setPhone(e.target.value)}
                      placeholder="例: 09012345678 / e.g. 09012345678"
                      className="bg-white border-gray-300 text-gray-900 h-9 flex-1"
                    />
                    <Button 
                      onClick={handleSendOtp} 
                      disabled={isSendingOtp}
                      size="sm"
                      className="bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold h-9 whitespace-nowrap"
                    >
                      {isSendingOtp ? '...' : t('SMS送信', lang)}
                    </Button>
                  </div>
                  <p className="text-gray-500 text-[10px]">国際形式（+81...）でも入力可 / International format also accepted</p>
                </div>
                
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">{t('認証コード', lang)} / Verification Code</Label>
                  <div className="flex gap-2">
                    <Input 
                      type="text" 
                      value={otpCode} 
                      onChange={e => setOtpCode(e.target.value)}
                      placeholder="6桁のコード / 6-digit code"
                      maxLength={6}
                      className="bg-white border-gray-300 text-gray-900 h-9 flex-1"
                    />
                    <Button 
                      onClick={handleVerifyOtp} 
                      disabled={isVerifyingOtp}
                      size="sm"
                      className="bg-white text-gray-950 hover:bg-white/90 font-bold h-9 px-4 whitespace-nowrap"
                    >
                      {isVerifyingOtp ? '...' : t('認証する', lang)}
                    </Button>
                  </div>
                  {isDebugMode && (
                    <p className="text-gray-500 text-[10px]">デモ環境: 認証コードは 000000 / Demo: use code 000000</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {isAuthenticated && token && <MypageSecurityPanel />}

        {/* Quick Actions */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-10">
          <Link href="/orders">
            <div className="bg-gray-50 rounded-lg border border-gray-200 p-4 flex items-center gap-3 hover:border-yellow-400/30 transition-colors cursor-pointer group">
              <div className="p-2 rounded-md bg-yellow-400/10 text-yellow-400 group-hover:bg-yellow-400 group-hover:text-gray-950 transition-colors">
                <Package className="h-5 w-5" />
              </div>
              <div>
                <p className="text-gray-900 font-medium text-sm">{t('注文履歴', lang)}</p>
                <p className="text-gray-500 text-[10px]">{isLoading ? t('読み込み中...', lang) : lang === 'ja' ? `${orders.length}件の最近の注文` : `${orders.length} recent orders`}</p>
              </div>
            </div>
          </Link>
          <Link href="/mypage/favorites">
            <div className="bg-gray-50 rounded-lg border border-gray-200 p-4 flex items-center gap-3 hover:border-pink-400/30 transition-colors cursor-pointer group">
              <div className="p-2 rounded-md bg-pink-400/10 text-pink-400 group-hover:bg-pink-400 group-hover:text-white transition-colors">
                <Heart className="h-5 w-5" />
              </div>
              <div>
                <p className="text-gray-900 font-medium text-sm">{t('お気に入り', lang)}</p>
                <p className="text-gray-500 text-[10px]">
                  {favoriteCount === null
                    ? t('読み込み中...', lang)
                    : lang === 'ja'
                      ? `${favoriteCount}件`
                      : `${favoriteCount} items`}
                </p>
              </div>
            </div>
          </Link>
          <Link href="/mypage/profile">
            <div className="bg-gray-50 rounded-lg border border-gray-200 p-4 flex items-center gap-3 hover:border-violet-400/30 transition-colors cursor-pointer group">
              <div className="p-2 rounded-md bg-violet-400/10 text-violet-500 group-hover:bg-violet-500 group-hover:text-white transition-colors">
                <UserRound className="h-5 w-5" />
              </div>
              <div>
                <p className="text-gray-900 font-medium text-sm">{lang === 'ja' ? 'お客様情報' : 'Customer info'}</p>
                <p className="text-gray-500 text-[10px]">
                  {user?.family_name && user?.given_name ? t('登録済み', lang) : t('未登録', lang)}
                </p>
              </div>
            </div>
          </Link>
          <Link href="/mypage/addresses">
            <div className="bg-gray-50 rounded-lg border border-gray-200 p-4 flex items-center gap-3 hover:border-blue-400/30 transition-colors cursor-pointer group">
              <div className="p-2 rounded-md bg-blue-400/10 text-blue-400 group-hover:bg-blue-400 group-hover:text-white transition-colors">
                <MapPin className="h-5 w-5" />
              </div>
              <div>
                <p className="text-gray-900 font-medium text-sm">{t('住所管理', lang)}</p>
                <p className="text-gray-500 text-[10px]">
                  {user?.postal_code ? t('登録済み', lang) : t('未登録', lang)}
                </p>
              </div>
            </div>
          </Link>
          <Link href="/mypage/inquiries/new">
            <div className="bg-gray-50 rounded-lg border border-gray-200 p-4 flex items-center gap-3 hover:border-emerald-400/30 transition-colors cursor-pointer group">
              <div className="p-2 rounded-md bg-emerald-400/10 text-emerald-500 group-hover:bg-emerald-500 group-hover:text-white transition-colors">
                <MessageSquare className="h-5 w-5" />
              </div>
              <div>
                <p className="text-gray-900 font-medium text-sm">{lang === 'ja' ? 'お問い合わせ' : 'Contact'}</p>
                <p className="text-gray-500 text-[10px]">{lang === 'ja' ? 'ショップへ連絡' : 'Message the shop'}</p>
              </div>
            </div>
          </Link>
          <Link href="/mypage/inquiries">
            <div className="bg-gray-50 rounded-lg border border-gray-200 p-4 flex items-center gap-3 hover:border-violet-400/30 transition-colors cursor-pointer group">
              <div className="p-2 rounded-md bg-violet-400/10 text-violet-500 group-hover:bg-violet-500 group-hover:text-white transition-colors">
                <Mail className="h-5 w-5" />
              </div>
              <div>
                <p className="text-gray-900 font-medium text-sm">{lang === 'ja' ? '問い合わせ履歴' : 'Inquiries'}</p>
                <p className="text-gray-500 text-[10px]">
                  {inquiryUnreadCount === null
                    ? t('読み込み中...', lang)
                    : inquiryUnreadCount > 0
                      ? lang === 'ja'
                        ? `未読 ${inquiryUnreadCount}件`
                        : `${inquiryUnreadCount} unread`
                      : lang === 'ja'
                        ? '履歴を見る'
                        : 'View history'}
                </p>
              </div>
            </div>
          </Link>
          <Link href="/mypage/announcements">
            <div className="bg-gray-50 rounded-lg border border-gray-200 p-4 flex items-center gap-3 hover:border-amber-400/30 transition-colors cursor-pointer group">
              <div className="p-2 rounded-md bg-amber-400/10 text-amber-500 group-hover:bg-amber-500 group-hover:text-white transition-colors relative">
                <Bell className="h-5 w-5" />
                {announcementUnreadCount != null && announcementUnreadCount > 0 && (
                  <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center">
                    {announcementUnreadCount > 9 ? '9+' : announcementUnreadCount}
                  </span>
                )}
              </div>
              <div>
                <p className="text-gray-900 font-medium text-sm">{t('お知らせ', lang)}</p>
                <p className="text-gray-500 text-[10px]">
                  {announcementUnreadCount === null
                    ? t('読み込み中...', lang)
                    : announcementUnreadCount > 0
                      ? lang === 'ja'
                        ? `未読 ${announcementUnreadCount}件`
                        : `${announcementUnreadCount} unread`
                      : lang === 'ja'
                        ? '一覧を見る'
                        : 'View announcements'}
                </p>
              </div>
            </div>
          </Link>
        </div>

        {/* Recent Orders */}
        <div className="mb-12">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-gray-900 font-semibold flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-gray-500" /> {t('最近の注文', lang)}
            </h2>
            <Link href="/orders" className="text-yellow-400 text-xs hover:text-yellow-300">
              {t('すべて見る', lang)} →
            </Link>
          </div>
          {isLoading ? (
            <div className="space-y-2">
              {[1, 2].map((i) => (
                <div key={i} className="h-16 bg-gray-50 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : orders.length === 0 ? (
            <div className="bg-gray-50 rounded-lg border border-dashed border-gray-200 p-8 text-center">
              <p className="text-gray-500 text-sm">{t('注文履歴はありません', lang)}</p>
            </div>
          ) : (
            <div className="space-y-2">
              {orders.map((order) => (
                <div key={order.id} className="flex justify-between items-center bg-gray-50 rounded-lg border border-gray-200 p-4 hover:border-gray-300 transition-colors">
                  <div>
                    <p className="text-gray-900 text-sm font-medium">{t('注文番号', lang)} #{order.id}</p>
                    <p className="text-gray-500 text-[10px]">
                      {order.created_at ? new Date(order.created_at).toLocaleDateString(lang === 'ja' ? 'ja-JP' : 'en-US') : '不明'}
                    </p>
                  </div>
                  <div className="text-right">
                    <span className="text-yellow-400 font-bold block text-sm">{formatPrice(order.total_amount || 0)}</span>
                    <span className="text-[10px] text-gray-500">{t(order.status, lang)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Danger Zone */}
        <div className="mt-12 pt-8 border-t border-gray-100">
          <div className="bg-red-500/5 rounded-xl border border-red-500/10 p-6">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
              <h2 className="text-lg font-bold text-gray-900">{t('危険領域', lang)}</h2>
            </div>
            <p className="text-gray-400 text-xs mb-4 leading-relaxed">
              {t('アカウントを削除すると、これまでの注文履歴や登録情報がすべて失われます。この操作は取り消せません。', lang)}
            </p>
            <Button
              variant="ghost"
              disabled={isDeleting}
              onClick={handleDeleteAccount}
              className="text-red-500 hover:text-gray-900 hover:bg-red-500 flex items-center gap-2 transition-all border border-red-500/20 text-xs h-9"
            >
              <Trash2 className="h-4 w-4" />
              {isDeleting ? t('更新中...', lang) : t('アカウントを完全に削除する', lang)}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
