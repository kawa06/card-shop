import CardDetailClient from './CardDetailClient'

export async function generateStaticParams() {
  return []
}

export default function CardDetailPage({ params }: { params: { id: string } }) {
  return <CardDetailClient id={params.id} />
}
