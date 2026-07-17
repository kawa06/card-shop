import Link from 'next/link'
import Image from 'next/image'
import { SignIn } from '@clerk/nextjs'
import { clerkAppearance } from '@/lib/clerk/appearance'

export default function SignInPage() {
  return (
    <div className="min-h-[70vh] bg-white flex items-center justify-center p-4 overflow-x-hidden w-full max-w-full clerk-auth-page">
      <div className="w-full max-w-md overflow-x-hidden">
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2 text-2xl font-bold">
            <div className="relative h-10 w-10 flex-shrink-0 overflow-hidden rounded-md border border-yellow-400/20">
              <Image
                src="/logo-main.png"
                alt="KRX TCG"
                fill
                className="object-contain"
                priority
              />
            </div>
            <span className="text-gray-900">KRX TCG</span>
          </Link>
          <p className="text-gray-500 mt-2 text-sm">メールアドレスでログイン</p>
        </div>
        <SignIn
          appearance={clerkAppearance}
          routing="path"
          path="/sign-in"
          signUpUrl="/sign-up"
          fallbackRedirectUrl="/auth/after-sign-in"
        />
      </div>
    </div>
  )
}
