import CardDetailClient from './CardDetailClient'

export async function generateStaticParams() {
  return [{ id: '1' }]
}

export default function CardDetailPage({ params }: { params: { id: string } }) {
  return <CardDetailClient id={params.id} />
}
