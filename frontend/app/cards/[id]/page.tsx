import { Metadata } from 'next'
import { notFound } from 'next/navigation'
import CardDetailClient from './CardDetailClient'
import { JsonLd } from '@/components/seo/JsonLd'
import {
  absoluteUrl,
  buildBreadcrumbJsonLd,
  buildProductJsonLd,
} from '@/lib/seo'

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ||
  'https://backend-production-054e.up.railway.app'

async function getCard(id: string) {
  try {
    const res = await fetch(`${API_BASE}/api/cards/${id}`, {
      next: { revalidate: 3600 },
    })
    if (!res.ok) return null
    return res.json()
  } catch (error) {
    console.error('Fetch error:', error)
    return null
  }
}

export async function generateMetadata(
  { params }: { params: { id: string } }
): Promise<Metadata> {
  const card = await getCard(params.id)

  if (!card) {
    return {
      title: 'カードが見つかりませんでした',
      robots: { index: false, follow: false },
    }
  }

  const conditionLabel: Record<string, string> = {
    a: 'A（美品）',
    b: 'B（良品）',
    c: 'C（並品）',
    d: 'D（傷あり）',
    e: 'E（難あり）',
  }
  const condition = conditionLabel[card.condition] || card.condition.toUpperCase()

  const title = `${card.name}（${condition}）`
  const description = `${card.name} - ${card.price.toLocaleString()}円 / 状態${condition} / 在庫${card.stock}点`
  const canonical = absoluteUrl(`/cards/${card.id}`)

  return {
    title,
    description,
    alternates: {
      canonical,
    },
    openGraph: {
      title,
      description,
      type: 'website',
      url: canonical,
      images: card.image_url ? [card.image_url] : ['/ogp.png'],
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
      images: card.image_url ? [card.image_url] : ['/ogp.png'],
    },
  }
}

export default async function CardDetailPage({ params }: { params: { id: string } }) {
  const card = await getCard(params.id)

  if (!card) {
    notFound()
  }

  const productJsonLd = buildProductJsonLd(card)
  const breadcrumbJsonLd = buildBreadcrumbJsonLd([
    { name: 'トップ', path: '/' },
    { name: card.name, path: `/cards/${card.id}` },
  ])

  return (
    <>
      <JsonLd data={[productJsonLd, breadcrumbJsonLd]} />
      <CardDetailClient id={params.id} />
    </>
  )
}
