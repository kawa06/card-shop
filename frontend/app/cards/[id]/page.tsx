import CardDetailClient from './CardDetailClient'

export default function CardDetailPage({ params }: { params: { id: string } }) {
  return <CardDetailClient id={params.id} />
}
