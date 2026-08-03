'use client'

import { useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { adminBuybackApi } from '@/lib/api'

export default function BuybackRequestDetailRedirectPage() {
  const params = useParams()
  const router = useRouter()
  const { isReady } = useAdminGuard()
  const id = Number(params.id)

  useEffect(() => {
    if (!isReady || !id || Number.isNaN(id)) return
    void adminBuybackApi.getRequest(id).then((res) => {
      const method = res.data.buyback_method || (res.data.is_store_purchase ? 'store' : 'mail')
      const base = method === 'store' ? '/admin/buyback/store/requests' : '/admin/buyback/mail/requests'
      router.replace(`${base}/${id}`)
    }).catch(() => {
      router.replace('/admin/buyback/requests')
    })
  }, [isReady, id, router])

  return <p className="container py-12 text-gray-500">読み込み中...</p>
}
