'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, UserCheck } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminBuybackApi } from '@/lib/api'
import { AdminIdentityDetail } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('ja-JP')
}

export default function AdminBuybackKycDetailPage() {
  const params = useParams()
  const router = useRouter()
  const { isReady } = useAdminGuard()
  const id = Number(params.id)
  const [detail, setDetail] = useState<AdminIdentityDetail | null>(null)
  const [frontUrl, setFrontUrl] = useState<string | null>(null)
  const [backUrl, setBackUrl] = useState<string | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const loadDocuments = useCallback(async (identityId: number, hasFront: boolean, hasBack: boolean) => {
    const urls: { front?: string; back?: string } = {}
    try {
      if (hasFront) {
        const res = await adminBuybackApi.getIdentityDocument(identityId, 'front')
        urls.front = URL.createObjectURL(res.data)
      }
      if (hasBack) {
        const res = await adminBuybackApi.getIdentityDocument(identityId, 'back')
        urls.back = URL.createObjectURL(res.data)
      }
    } catch {
      /* images may be unavailable in prod without R2 */
    }
    setFrontUrl(urls.front || null)
    setBackUrl(urls.back || null)
  }, [])

  const fetchDetail = useCallback(async () => {
    if (!id || Number.isNaN(id)) return
    setIsLoading(true)
    setError('')
    try {
      const res = await adminBuybackApi.getIdentity(id)
      setDetail(res.data)
      await loadDocuments(res.data.id, res.data.has_front, res.data.has_back)
    } catch {
      setError('本人確認情報の取得に失敗しました')
    } finally {
      setIsLoading(false)
    }
  }, [id, loadDocuments])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void fetchDetail()
    return () => {
      if (frontUrl) URL.revokeObjectURL(frontUrl)
      if (backUrl) URL.revokeObjectURL(backUrl)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isMounted, isReady, fetchDetail])

  const handleApprove = async () => {
    if (!detail) return
    setIsSaving(true)
    setError('')
    try {
      await adminBuybackApi.approveIdentity(detail.id)
      router.push('/admin/buyback/kyc')
    } catch {
      setError('承認に失敗しました')
    } finally {
      setIsSaving(false)
    }
  }

  const handleReject = async () => {
    if (!detail) return
    if (!rejectReason.trim()) {
      setError('差戻し理由を入力してください')
      return
    }
    setIsSaving(true)
    setError('')
    try {
      await adminBuybackApi.rejectIdentity(detail.id, rejectReason.trim())
      router.push('/admin/buyback/kyc')
    } catch {
      setError('差戻しに失敗しました')
    } finally {
      setIsSaving(false)
    }
  }

  if (!isMounted || !isReady) return null

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-4xl">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/admin/buyback/kyc" className="text-gray-500 hover:text-gray-900">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <UserCheck className="h-6 w-6 text-yellow-400" />
          <h1 className="text-2xl font-bold text-gray-900">KYC 詳細</h1>
        </div>

        {isLoading ? (
          <p className="text-gray-500">読み込み中...</p>
        ) : !detail ? (
          <p className="text-red-600">{error || 'データが見つかりません'}</p>
        ) : (
          <div className="space-y-6">
            <div className="border rounded-lg p-4 space-y-2 text-sm">
              <p>
                <span className="text-gray-500">会員：</span>
                {detail.user_name}（{detail.user_email}）
              </p>
              <p>
                <span className="text-gray-500">書類：</span>
                {detail.document_type_label || '—'}
              </p>
              <p>
                <span className="text-gray-500">ステータス：</span>
                {detail.status_label}
              </p>
              <p>
                <span className="text-gray-500">提出：</span>
                {formatDate(detail.submitted_at)}
              </p>
              {detail.rejection_reason && (
                <p className="text-red-600">
                  <span className="text-gray-500">差戻し理由：</span>
                  {detail.rejection_reason}
                </p>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {frontUrl ? (
                <div>
                  <p className="text-sm text-gray-500 mb-2">表面</p>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={frontUrl} alt="本人確認（表面）" className="w-full rounded border" />
                </div>
              ) : detail.has_front ? (
                <p className="text-sm text-gray-500">表面画像を読み込めませんでした</p>
              ) : null}
              {backUrl ? (
                <div>
                  <p className="text-sm text-gray-500 mb-2">裏面</p>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={backUrl} alt="本人確認（裏面）" className="w-full rounded border" />
                </div>
              ) : detail.has_back ? (
                <p className="text-sm text-gray-500">裏面画像を読み込めませんでした</p>
              ) : null}
            </div>

            {detail.status === 'pending' && (
              <div className="border rounded-lg p-4 space-y-4">
                <Input
                  placeholder="差戻し理由（差戻し時のみ）"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                />
                {error && <p className="text-sm text-red-600">{error}</p>}
                <div className="flex flex-wrap gap-3">
                  <Button onClick={handleApprove} disabled={isSaving}>
                    承認する
                  </Button>
                  <Button variant="outline" onClick={handleReject} disabled={isSaving}>
                    差戻しする
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
