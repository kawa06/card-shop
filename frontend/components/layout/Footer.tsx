import Link from 'next/link'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'

export default function Footer() {
  const { lang } = useLangStore()

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
              {lang === 'ja' 
                ? 'トレーディングカードの専門ショップ。レアカードから初心者向けカードまで豊富なラインナップ。'
                : 'A specialty shop for trading cards. From rare cards to beginner-friendly ones, we have a wide selection.'}
            </p>
          </div>

          <div>
            <h4 className="text-white font-semibold mb-3">{t('ショップ', lang)}</h4>
            <ul className="space-y-2 text-sm">
              <li><Link href="/" className="hover:text-yellow-400 transition-colors">{t('カード一覧', lang)}</Link></li>
              <li><Link href="/cart" className="hover:text-yellow-400 transition-colors">{t('カート', lang)}</Link></li>
              <li><Link href="/orders" className="hover:text-yellow-400 transition-colors">{t('注文履歴', lang)}</Link></li>
              <li><Link href="/mypage" className="hover:text-yellow-400 transition-colors">{t('マイページ', lang)}</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="text-white font-semibold mb-3">{t('規約・情報', lang)}</h4>
            <ul className="space-y-2 text-sm">
              <li><Link href="/terms" className="hover:text-yellow-400 transition-colors">{t('利用規約', lang)}</Link></li>
              <li><Link href="/privacy" className="hover:text-yellow-400 transition-colors">{t('プライバシーポリシー', lang)}</Link></li>
              <li><Link href="#" className="hover:text-yellow-400 transition-colors opacity-50 cursor-not-allowed">{t('特定商取引法に基づく表記', lang)}</Link></li>
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
