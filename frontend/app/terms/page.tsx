'use client'

import { ArrowLeft } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import { Button } from '@/components/ui/button'

export default function TermsPage() {
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

        <h1 className="text-3xl font-bold text-white mb-8">{t('利用規約', lang)}</h1>

        <div className="bg-gray-900 rounded-xl border border-white/10 p-8 space-y-6 text-gray-300 leading-relaxed">
          <section>
            <h2 className="text-xl font-bold text-white mb-3">{t('第1条（適用）', lang)}</h2>
            <p>
              {lang === 'ja'
                ? '本規約は，ユーザーと当ショップ（以下，「当ショップ」といいます。）との間の本サービスの利用に関わる一切の関係に適用されるものとします。'
                : 'These terms shall apply to all relations between the user and our shop (hereinafter referred to as "the Shop") regarding the use of this service.'}
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold text-white mb-3">{t('第2条（利用登録）', lang)}</h2>
            <p>
              {lang === 'ja'
                ? '登録希望者が当ショップの定める方法によって利用登録を申請し，当ショップがこれを承認することによって，利用登録が完了するものとします。'
                : 'Registration shall be completed when the applicant applies for registration by the method specified by the Shop and the Shop approves it.'}
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold text-white mb-3">{t('第3条（禁止事項）', lang)}</h2>
            <p>{lang === 'ja' ? 'ユーザーは，本サービスの利用にあたり，以下の行為をしてはなりません。' : 'In using this service, the user must not engage in the following acts:'}</p>
            <ul className="list-disc ml-6 mt-2 space-y-1">
              <li>{lang === 'ja' ? '法令または公序良俗に違反する行為' : 'Acts that violate laws or public order and morals'}</li>
              <li>{lang === 'ja' ? '犯罪行為に関連する行為' : 'Acts related to criminal behavior'}</li>
              <li>{lang === 'ja' ? '当ショップのサーバーまたはネットワークの機能を破壊したり，妨害したりする行為' : 'Acts that destroy or interfere with the functions of the Shop\'s servers or networks'}</li>
              <li>{lang === 'ja' ? '当ショップのサービスの運営を妨害するおそれのある行為' : 'Acts that may interfere with the operation of the Shop\'s services'}</li>
              <li>{lang === 'ja' ? '他のユーザーに関する個人情報等を収集または蓄積する行為' : 'Acts of collecting or accumulating personal information about other users'}</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-bold text-white mb-3">{t('第4条（免責事項）', lang)}</h2>
            <p>
              {lang === 'ja'
                ? '当ショップの債務不履行責任は，当ショップの故意または重過失によらない場合には免責されるものとします。'
                : 'The Shop shall be exempt from liability for default unless it is due to the Shop\'s intentional misconduct or gross negligence.'}
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold text-white mb-3">{t('第5条（準拠法・裁判管轄）', lang)}</h2>
            <p>
              {lang === 'ja'
                ? '本規約の解釈にあたっては，日本法を準拠法とします。本サービスに関して紛争が生じた場合には，当ショップの本店所在地を管轄する裁判所を専属的合意管轄とします。'
                : 'The interpretation of these terms shall be governed by Japanese law. In the event of a dispute regarding this service, the court having jurisdiction over the location of the Shop\'s head office shall be the exclusive agreed jurisdiction.'}
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
