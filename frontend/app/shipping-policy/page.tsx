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
                <p className="text-sm opacity-80">{t('600円（補償あり、推奨）', lang)}</p>
              </div>
              <div className="p-4 bg-gray-800 rounded-lg border border-white/5">
                <h3 className="font-bold text-white mb-1">{t('クリックポスト（日本郵便）', lang)}</h3>
                <p className="text-sm opacity-80">{t('200円（追跡あり・補償なし、安価）', lang)}</p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-yellow-400" />
              {t('補償内容', lang)}
            </h2>
            <div className="overflow-hidden rounded-lg border border-white/10">
              <table className="w-full text-left text-sm">
                <thead className="bg-white/5 text-white">
                  <tr>
                    <th className="px-4 py-3">{t('発送方法', lang)}</th>
                    <th className="px-4 py-3">{t('補償内容', lang)}</th>
                    <th className="px-4 py-3">{t('追跡サービス', lang)}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10">
                  <tr>
                    <td className="px-4 py-3">{t('宅急便コンパクト', lang)}</td>
                    <td className="px-4 py-3">{t('最大3万円相当（ヤマト運輸規定による）', lang)}</td>
                    <td className="px-4 py-3">{t('あり', lang)}</td>
                  </tr>
                  <tr>
                    <td className="px-4 py-3">{t('クリックポスト', lang)}</td>
                    <td className="px-4 py-3 text-red-400">{t('補償なし', lang)}</td>
                    <td className="px-4 py-3">{t('あり', lang)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section className="p-6 bg-red-400/5 rounded-xl border border-red-400/20">
            <h2 className="text-xl font-bold text-red-400 mb-3 flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              {t('重要免責事項', lang)}
            </h2>
            <p className="text-red-400 font-bold leading-relaxed">
              {t('お客様が安価な発送方法（クリックポスト等）を選択された場合、配送中の紛失・破損・遅延について当店は一切の責任を負いません。補償付き発送方法（宅急便コンパクト）の選択を推奨いたします。', lang)}
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
