'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { User, Package, Heart, MapPin, Trash2, AlertTriangle, Key, ShieldCheck, Mail, CheckCircle2 } from 'lucide-react'
import { useAuthStore } from '@/store/auth'
import { ordersApi, authApi } from '@/lib/api'
import { Order } from '@/lib/types'
import { usePrice } from '@/lib/format'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from '@/lib/use-toast'

export default function MypagePage() {
  const router = useRouter()
  const { isAuthenticated, user, logout, fetchMe } = useAuthStore()
  const { formatPrice, lang } = usePrice()
  const [orders, setOrders] = useState<Order[]>([])
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

  useEffect(() => {
    setIsMounted(true)
    if (!isAuthenticated) {
      router.push('/login')
      return
    }
    // Refresh user data to get latest verification status
    fetchMe()
    
    ordersApi.getAll().then((res) => {
      setOrders((res.data || []).slice(0, 3))
    }).catch(() => {}).finally(() => setIsLoading(false))
  }, [isAuthenticated, router, fetchMe])

  const handleDeleteAccount = async () => {
    const confirmed = confirm('本当にアカウントを削除しますか？この操作は取り消せません。')
    if (!confirmed) return

    setIsDeleting(true)
    try {
      await authApi.deleteAccount()
      toast({ title: 'アカウントを削除しました', description: 'ご利用ありがとうございました。' })
      logout()
      router.push('/')
    } catch {
      toast({ title: 'エラー', description: 'アカウントの削除に失敗しました。', variant: 'destructive' })
    } finally {
      setIsDeleting(false)
    }
  }

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    if (newPassword.length < 8) {
      toast({ title: 'エラー', description: '新しいパスワードは8文字以上で入力してください', variant: 'destructive' })
      return
    }

    setIsUpdatingPassword(true)
    try {
      await authApi.changePassword({ old_password: oldPassword, new_password: newPassword })
      toast({ title: '完了', description: 'パスワードを更新しました。' })
      setShowPasswordForm(false)
      setOldPassword('')
      setNewPassword('')
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'パスワードの変更に失敗しました。'
      toast({ title: 'エラー', description: msg, variant: 'destructive' })
    } finally {
      setIsUpdatingPassword(false)
    }
  }

  const handleRequestVerification = async () => {
    setIsRequestingVerify(true)
    try {
      const res = await authApi.requestVerification()
      toast({ 
        title: 'リクエスト送信', 
        description: res.data.message + (res.data.debug_token ? ` (Token: ${res.data.debug_token})` : '') 
      })
    } catch {
      toast({ title: 'エラー', description: '認証リクエストに失敗しました。', variant: 'destructive' })
    } finally {
      setIsRequestingVerify(false)
    }
  }

  if (!isMounted || !isAuthenticated || !user) return null

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="container py-8 max-w-3xl">
        <h1 className="text-2xl font-bold text-white mb-6">マイページ</h1>

        {/* Profile Card */}
        <div className="bg-gray-900 rounded-xl border border-white/10 p-6 mb-6">
          <div className="flex flex-col sm:flex-row sm:items-center gap-6">
            <div className="w-20 h-20 rounded-full bg-yellow-400/10 border border-yellow-400/20 flex items-center justify-center flex-shrink-0">
              <User className="h-10 w-10 text-yellow-400" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-xl font-bold text-white">{user.name}</h2>
                {user.is_admin && (
                  <span className="text-[10px] bg-yellow-400/20 text-yellow-400 px-2 py-0.5 rounded border border-yellow-400/20">
                    管理者
                  </span>
                )}
                {user.is_verified ? (
                  <span className="flex items-center gap-1 text-[10px] bg-green-500/20 text-green-400 px-2 py-0.5 rounded border border-green-500/20">
                    <CheckCircle2 className="h-3 w-3" /> 認証済み
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-[10px] bg-gray-500/20 text-gray-400 px-2 py-0.5 rounded border border-gray-500/20">
                    未認証
                  </span>
                )}
              </div>
              <p className="text-gray-400 text-sm mt-1">{user.email}</p>
              <p className="text-gray-500 text-xs mt-1">
                {user.postal_code && `〒${user.postal_code} `}
                {user.region}{user.city}{user.address_line1} {user.address_line2}
              </p>
              {user.address && !user.region && (
                <p className="text-gray-500 text-xs mt-1">{user.address}</p>
              )}
              
              {!user.is_verified && (
                <button 
                  onClick={handleRequestVerification}
                  disabled={isRequestingVerify}
                  className="text-yellow-400 text-xs mt-2 hover:underline disabled:opacity-50"
                >
                  {isRequestingVerify ? '処理中...' : '認証メールを再送する'}
                </button>
              )}
            </div>
            <div className="flex gap-2">
              <Button 
                variant="outline" 
                size="sm" 
                className="border-white/10 text-gray-300 hover:text-white"
                onClick={() => setShowPasswordForm(!showPasswordForm)}
              >
                <Key className="h-4 w-4 mr-2" />
                パスワード変更
              </Button>
            </div>
          </div>

          {/* Password Change Form */}
          {showPasswordForm && (
            <div className="mt-6 pt-6 border-t border-white/5 animate-in slide-in-from-top-2">
              <form onSubmit={handleChangePassword} className="space-y-4 max-w-sm">
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">現在のパスワード</Label>
                  <Input 
                    type="password" 
                    value={oldPassword} 
                    onChange={e => setOldPassword(e.target.value)}
                    required
                    className="bg-gray-800 border-gray-700 text-white h-9"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">新しいパスワード</Label>
                  <Input 
                    type="password" 
                    value={newPassword} 
                    onChange={e => setNewPassword(e.target.value)}
                    required
                    minLength={8}
                    className="bg-gray-800 border-gray-700 text-white h-9"
                  />
                </div>
                <div className="flex gap-2">
                  <Button type="submit" size="sm" disabled={isUpdatingPassword} className="bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold">
                    {isUpdatingPassword ? '更新中...' : 'パスワードを更新'}
                  </Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setShowPasswordForm(false)} className="text-gray-400">
                    キャンセル
                  </Button>
                </div>
              </form>
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10">
          <Link href="/orders">
            <div className="bg-gray-900 rounded-lg border border-white/10 p-4 flex items-center gap-3 hover:border-yellow-400/30 transition-colors cursor-pointer group">
              <div className="p-2 rounded-md bg-yellow-400/10 text-yellow-400 group-hover:bg-yellow-400 group-hover:text-gray-950 transition-colors">
                <Package className="h-5 w-5" />
              </div>
              <div>
                <p className="text-white font-medium text-sm">注文履歴</p>
                <p className="text-gray-500 text-[10px]">{isLoading ? '読み込み中' : `${orders.length}件の最近の注文`}</p>
              </div>
            </div>
          </Link>
          <div className="bg-gray-900 rounded-lg border border-white/10 p-4 flex items-center gap-3 opacity-50">
            <div className="p-2 rounded-md bg-pink-400/10 text-pink-400">
              <Heart className="h-5 w-5" />
            </div>
            <div>
              <p className="text-white font-medium text-sm">お気に入り</p>
              <p className="text-gray-500 text-[10px]">準備中</p>
            </div>
          </div>
          <div className="bg-gray-900 rounded-lg border border-white/10 p-4 flex items-center gap-3 opacity-50">
            <div className="p-2 rounded-md bg-blue-400/10 text-blue-400">
              <MapPin className="h-5 w-5" />
            </div>
            <div>
              <p className="text-white font-medium text-sm">住所管理</p>
              <p className="text-gray-500 text-[10px]">準備中</p>
            </div>
          </div>
        </div>

        {/* Recent Orders */}
        <div className="mb-12">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-white font-semibold flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-gray-500" /> 最近の注文
            </h2>
            <Link href="/orders" className="text-yellow-400 text-xs hover:text-yellow-300">
              すべて見る →
            </Link>
          </div>
          {isLoading ? (
            <div className="space-y-2">
              {[1, 2].map((i) => (
                <div key={i} className="h-16 bg-gray-900 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : orders.length === 0 ? (
            <div className="bg-gray-900/50 rounded-lg border border-dashed border-white/10 p-8 text-center">
              <p className="text-gray-500 text-sm">注文履歴はありません</p>
            </div>
          ) : (
            <div className="space-y-2">
              {orders.map((order) => (
                <div key={order.id} className="flex justify-between items-center bg-gray-900 rounded-lg border border-white/10 p-4 hover:border-white/20 transition-colors">
                  <div>
                    <p className="text-white text-sm font-medium">注文 #{order.id}</p>
                    <p className="text-gray-500 text-[10px]">
                      {order.created_at ? new Date(order.created_at).toLocaleDateString('ja-JP') : '不明'}
                    </p>
                  </div>
                  <div className="text-right">
                    <span className="text-yellow-400 font-bold block text-sm">{formatPrice(order.total_amount || 0)}</span>
                    <span className="text-[10px] text-gray-500">{order.status}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Danger Zone */}
        <div className="mt-12 pt-8 border-t border-white/5">
          <div className="bg-red-500/5 rounded-xl border border-red-500/10 p-6">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
              <h2 className="text-lg font-bold text-white">危険領域</h2>
            </div>
            <p className="text-gray-400 text-xs mb-4 leading-relaxed">
              アカウントを削除すると、これまでの注文履歴や登録情報がすべて失われます。この操作は取り消せません。
            </p>
            <Button
              variant="ghost"
              disabled={isDeleting}
              onClick={handleDeleteAccount}
              className="text-red-500 hover:text-white hover:bg-red-500 flex items-center gap-2 transition-all border border-red-500/20 text-xs h-9"
            >
              <Trash2 className="h-4 w-4" />
              {isDeleting ? '削除中...' : 'アカウントを完全に削除する'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
