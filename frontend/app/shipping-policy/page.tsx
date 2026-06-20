'use client'

import { ArrowLeft, Truck, ShieldCheck, AlertTriangle } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'

export default function ShippingPolicyPage() {
  const router = useRouter()
  const { lang } = useLangStore()

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="container py-8 max-w-3xl">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-gray-400 hover:text-white mb-6 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('戻る', lang)}
        </button>

        <h1 className="text-3xl font-bold text-white mb-8">{t('発送・補償ポリシー', lang)}</h1>

        <div className="bg-gray-900 rounded-xl border border-white/10 p-8 space-y-8 text-gray-300 leading-relaxed">
          <section>
            <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <Truck className="h-5 w-5 text-yellow-400" />
              {t('配送方法の種類', lang)}
            </h2>
            <div className="grid gap-4">
              <div className="p-4 bg-gray-800 rounded-lg border border-white/5">
                <h3 className="font-bold text-white mb-1">{t('宅急便コンパクト（ヤマト運輸）', lang)}</h3>
                <p className="text-sm opacity-80">{t('補償あり、推奨', lang)}</p>
              </div>
              <div className="p-4 bg-gray-800 rounded-lg border border-white/5">
                <h3 className="font-bold text-white mb-1">{t('クリックポスト（日本郵便）', lang)}</h3>
                <p className="text-sm opacity-80">{t('追跡あり・補償なし、安価', lang)}</p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-yellow-400" />
              {t('補償内容について', lang)}
            </h2>
            <div className="bg-gray-800 rounded-lg border border-white/5 p-6 space-y-4">
              <p className="text-sm text-gray-400 mb-4">
                {t('各配送方法の補償内容および利用規約については、以下の各社公式サイトをご確認ください。', lang)}
              </p>
              <div className="grid gap-3">
                <a
                  href="https://www.kuronekoyamato.co.jp/ytc/customer/send/services/compact/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between p-4 bg-white/5 hover:bg-white/10 rounded-lg border border-white/10 transition-colors group"
                >
                  <span className="font-bold text-white">{t('ヤマト運輸（宅急便コンパクト等）', lang)}</span>
                  <span className="text-xs text-yellow-400 group-hover:underline">{t('公式サイトで確認', lang)}</span>
                </a>
                <a
                  href="https://www.post.japanpost.jp/service/index.html"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between p-4 bg-white/5 hover:bg-white/10 rounded-lg border border-white/10 transition-colors group"
                >
                  <span className="font-bold text-white">{t('日本郵便（クリックポスト・ゆうパック等）', lang)}</span>
                  <span className="text-xs text-yellow-400 group-hover:underline">{t('公式サイトで確認', lang)}</span>
                </a>
              </div>
            </div>
          </section>

          <section className="p-6 bg-yellow-400/5 rounded-xl border border-yellow-400/20">
            <h2 className="text-xl font-bold text-yellow-400 mb-3 flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              {t('配送に関するご注意', lang)}
            </h2>
            <p className="text-gray-300 leading-relaxed">
              {t('配送中の事故（紛失・破損等）については、各配送会社の補償規定に基づき対応が行われます。万が一のトラブルの際、当店では各社の規定を超える責任は負いかねますので、補償内容を十分にご確認の上、発送方法をご選択ください。', lang)}
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
