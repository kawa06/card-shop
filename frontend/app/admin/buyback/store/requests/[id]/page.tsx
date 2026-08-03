'use client'

import { useParams } from 'next/navigation'
import { BuybackRequestDetailView } from '@/components/admin/buyback/BuybackRequestDetailView'

export default function StoreBuybackRequestDetailPage() {
  const params = useParams()
  const id = Number(params.id)
  return <BuybackRequestDetailView id={id} channel="store" />
}
