import { Metadata } from 'next'
import CardDetailClient from './CardDetailClient'

async function getCard(id: string) {
  try {
    const res = await fetch(`https://backend-production-054e.up.railway.app/api/cards/${id}`, {
      next: { revalidate: 3600 }
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

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      type: 'website',
      images: [card.image_url],
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
      images: [card.image_url],
    },
  }
}

export default async function CardDetailPage({ params }: { params: { id: string } }) {
  const card = await getCard(params.id)
  
  const jsonLd = card ? {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: card.name,
    image: card.image_url,
    description: card.description || `${card.name} - 状態${card.condition}`,
    sku: card.id.toString(),
    offers: {
      '@type': 'Offer',
      price: card.price,
      priceCurrency: 'JPY',
      availability: card.stock > 0 ? 'https://schema.org/InStock' : 'https://schema.org/OutOfStock',
      url: `https://frontend-one-topaz-20.vercel.app/cards/${card.id}`,
    },
  } : null

  return (
    <>
      {jsonLd && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      )}
      <CardDetailClient id={params.id} />
    </>
  )
}