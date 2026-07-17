'use client'

import { ArrowLeft, Truck, ShieldCheck, AlertTriangle, ExternalLink, Check, X } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import {
  SHIPPING_POLICY_INTRO,
  SHIPPING_POLICY_INTRO_EN,
  SHIPPING_METHODS,
  SHIPPING_COMPENSATION_SECTIONS,
  SHIPPING_CARRIER_LINKS,
  SHIPPING_POLICY_REVISED,
} from '@/lib/legal/shipping-policy'

export default function ShippingPolicyPage() {
  const router = useRouter()
  const { lang } = useLangStore()
  const isJa = lang === 'ja'

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-8 max-w-3xl">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-gray-400 hover:text-gray-900 mb-6 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('戻る', lang)}
        </button>

        <h1 className="text-3xl font-bold text-gray-900 mb-2">{t('発送・補償ポリシー', lang)}</h1>
        <p className="text-sm text-gray-400 mb-8">
          {isJa ? `最終更新: ${SHIPPING_POLICY_REVISED}` : `Last updated: ${SHIPPING_POLICY_REVISED}`}
        </p>

        <div className="bg-gray-50 rounded-xl border border-gray-200 p-8 space-y-10 text-gray-600 leading-relaxed">
          <p>{isJa ? SHIPPING_POLICY_INTRO : SHIPPING_POLICY_INTRO_EN}</p>

          <section>
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
              <Truck className="h-5 w-5 text-yellow-400" />
              {t('配送方法の種類', lang)}
            </h2>
            <div className="grid gap-4">
              {SHIPPING_METHODS.map((method) => (
                <div
                  key={method.code}
                  className={`p-5 bg-white rounded-lg border ${
                    method.recommended ? 'border-yellow-400/40 ring-1 ring-yellow-400/20' : 'border-gray-100'
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
                    <div>
                      <h3 className="font-bold text-gray-900">
                        {isJa ? method.nameJa : method.nameEn}
                      </h3>
                      <p className="text-sm text-gray-500 mt-0.5">
                        {isJa ? method.feeNote : method.feeNoteEn}
                      </p>
                    </div>
                    {method.recommended && (
                      <span className="text-xs font-bold px-2 py-1 rounded bg-yellow-400/20 text-yellow-600 border border-yellow-400/30">
                        {t('推奨', lang)}
                      </span>
                    )}
                  </div>

                  <div className="grid sm:grid-cols-2 gap-3 text-sm">
                    <div className="flex items-center gap-2">
                      {method.tracking ? (
                        <Check className="h-4 w-4 text-green-500 shrink-0" />
                      ) : (
                        <X className="h-4 w-4 text-gray-300 shrink-0" />
                      )}
                      <span>{t('追跡', lang)}: {method.tracking ? t('あり', lang) : t('なし', lang)}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {method.insurance ? (
                        <ShieldCheck className="h-4 w-4 text-green-500 shrink-0" />
                      ) : (
                        <AlertTriangle className="h-4 w-4 text-orange-400 shrink-0" />
                      )}
                      <span>
                        {t('補償', lang)}: {method.insurance ? t('あり', lang) : t('補償なし', lang)}
                      </span>
                    </div>
                    <div className="sm:col-span-2">
                      <span className="text-gray-400">{t('サイズ制限', lang)}: </span>
                      {isJa ? method.sizeLimit : method.sizeLimitEn}
                    </div>
                    <div className="sm:col-span-2">
                      <span className="text-gray-400">{t('目安配送日数', lang)}: </span>
                      {isJa ? method.deliveryDays : method.deliveryDaysEn}
                    </div>
                    <div className="sm:col-span-2">
                      <span className="text-gray-400">{t('補償内容', lang)}: </span>
                      {isJa ? method.insuranceDetail : method.insuranceDetailEn}
                    </div>
                  </div>

                  <a
                    href={method.sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 mt-3 text-xs text-yellow-500 hover:underline"
                  >
                    {t('公式サイトで確認', lang)}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              ))}
            </div>
          </section>

          {SHIPPING_COMPENSATION_SECTIONS.map((section) => (
            <section key={section.title}>
              <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-yellow-400" />
                {isJa ? section.title : section.titleEn}
              </h2>
              <div className="bg-white rounded-lg border border-gray-100 p-6 space-y-3">
                {(isJa ? section.paragraphs : section.paragraphsEn).map((p, i) => (
                  <p key={i} className="text-sm">{p}</p>
                ))}
              </div>
            </section>
          ))}

          <section>
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-yellow-400" />
              {t('補償内容について', lang)}
            </h2>
            <div className="bg-white rounded-lg border border-gray-100 p-6 space-y-4">
              <p className="text-sm text-gray-400">
                {t('各配送方法の補償内容および利用規約については、以下の各社公式サイトをご確認ください。', lang)}
              </p>
              <div className="grid gap-3">
                {SHIPPING_CARRIER_LINKS.map((link) => (
                  <a
                    key={link.url}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 rounded-lg border border-gray-200 transition-colors group"
                  >
                    <span className="font-bold text-gray-900 text-sm">
                      {isJa ? link.labelJa : link.labelEn}
                    </span>
                    <span className="text-xs text-yellow-400 group-hover:underline flex items-center gap-1">
                      {t('公式サイトで確認', lang)}
                      <ExternalLink className="h-3 w-3" />
                    </span>
                  </a>
                ))}
              </div>
            </div>
          </section>

          <section className="p-6 bg-yellow-400/5 rounded-xl border border-yellow-400/20">
            <h2 className="text-xl font-bold text-yellow-600 mb-3 flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              {t('配送に関するご注意', lang)}
            </h2>
            <p className="text-gray-600 leading-relaxed text-sm">
              {t('配送中の事故（紛失・破損等）については、各配送会社の補償規定に基づき対応が行われます。万が一のトラブルの際、当店では各社の規定を超える責任は負いかねますので、補償内容を十分にご確認の上、発送方法をご選択ください。', lang)}
            </p>
            <p className="text-gray-600 leading-relaxed text-sm mt-3">
              {t('お客様が安価な発送方法（レターパック等）を選択された場合、配送中の紛失・破損・遅延について当店は一切の責任を負いません。補償付き発送方法（宅急便コンパクト）の選択を推奨いたします。', lang)}
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
