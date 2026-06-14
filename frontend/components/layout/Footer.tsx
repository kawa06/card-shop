import Link from 'next/link'

export default function Footer() {
  return (
    <footer className="border-t border-white/10 bg-gray-950 text-gray-400">
      <div className="container py-10">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div>
            <h3 className="text-white font-bold text-lg mb-3 flex items-center gap-2">
              <span className="text-yellow-400">✦</span>
              Oripa_kawa
            </h3>
            <p className="text-sm leading-relaxed">
              トレーディングカードの専門ショップ。レアカードから初心者向けカードまで豊富なラインナップ。
            </p>
          </div>

          <div>
            <h4 className="text-white font-semibold mb-3">ショップ</h4>
            <ul className="space-y-2 text-sm">
              <li><Link href="/" className="hover:text-yellow-400 transition-colors">カード一覧</Link></li>
              <li><Link href="/cart" className="hover:text-yellow-400 transition-colors">カート</Link></li>
              <li><Link href="/orders" className="hover:text-yellow-400 transition-colors">注文履歴</Link></li>
              <li><Link href="/mypage" className="hover:text-yellow-400 transition-colors">マイページ</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="text-white font-semibold mb-3">アカウント</h4>
            <ul className="space-y-2 text-sm">
              <li><Link href="/login" className="hover:text-yellow-400 transition-colors">ログイン</Link></li>
              <li><Link href="/register" className="hover:text-yellow-400 transition-colors">会員登録</Link></li>
            </ul>
          </div>
        </div>

        <div className="border-t border-white/10 mt-8 pt-6 text-center text-sm">
          <p>&copy; {new Date().getFullYear()} Oripa_kawa. All rights reserved.</p>
        </div>
      </div>
    </footer>
  )
}
