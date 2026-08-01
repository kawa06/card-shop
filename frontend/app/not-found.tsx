import Link from 'next/link'
import { Button } from '@/components/ui/button'

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center px-6">
      <div className="max-w-md text-center space-y-4">
        <p className="text-sm font-semibold text-yellow-600">404</p>
        <h1 className="text-2xl font-bold text-gray-900">ページが見つかりません</h1>
        <p className="text-gray-600 text-sm">
          お探しのページは移動または削除された可能性があります。
        </p>
        <Link href="/">
          <Button className="bg-yellow-400 text-gray-950 hover:bg-yellow-300 font-bold">
            トップへ戻る
          </Button>
        </Link>
      </div>
    </div>
  )
}
