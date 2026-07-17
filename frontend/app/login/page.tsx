import { redirect } from 'next/navigation'

export default function LoginPage({
  searchParams,
}: {
  searchParams: { next?: string }
}) {
  const next = searchParams.next
  redirect(next ? `/sign-in?redirect_url=${encodeURIComponent(next)}` : '/sign-in')
}
