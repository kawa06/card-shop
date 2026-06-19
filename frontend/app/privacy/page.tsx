'use client'

import { ArrowLeft } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'

export default function PrivacyPage() {
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

        <h1 className="text-3xl font-bold text-white mb-8">{t('プライバシーポリシー', lang)}</h1>

        <div className="bg-gray-900 rounded-xl border border-white/10 p-8 space-y-6 text-gray-300 leading-relaxed">
          <p>
            {lang === 'ja'
              ? '当ショップは，本ウェブサイト上で提供するサービス（以下,「本サービス」といいます。）における，ユーザーの個人情報の取扱いについて，以下のとおりプライバシーポリシー（以下，「本ポリシー」といいます。）を定めます。'
              : 'The Shop establishes the following privacy policy (hereinafter referred to as "this Policy") regarding the handling of users\' personal information in the services provided on this website (hereinafter referred to as "the Service").'}
          </p>

          <section>
            <h2 className="text-xl font-bold text-white mb-3">{t('第1条（個人情報の収集方法）', lang)}</h2>
            <p>
              {lang === 'ja'
                ? '当ショップは，ユーザーが利用登録をする際に氏名，生年月日，住所，電話番号，メールアドレス，銀行口座番号，クレジットカード番号などの個人情報をお尋ねすることがあります。'
                : 'The Shop may ask for personal information such as name, date of birth, address, telephone number, email address, bank account number, and credit card number when a user registers for use.'}
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold text-white mb-3">{t('第2条（個人情報を収集・利用する目的）', lang)}</h2>
            <p>{lang === 'ja' ? '当ショップが個人情報を収集・利用する目的は，以下のとおりです。' : 'The purposes for which the Shop collects and uses personal information are as follows:'}</p>
            <ul className="list-disc ml-6 mt-2 space-y-1">
              <li>{lang === 'ja' ? '当ショップサービスの提供・運営のため' : 'For the provision and operation of the Shop\'s services'}</li>
              <li>{lang === 'ja' ? 'ユーザーからのお問い合わせに回答するため' : 'To respond to inquiries from users'}</li>
              <li>{lang === 'ja' ? 'ユーザーが利用中のサービスの新機能，更新情報，キャンペーン等及び当ショップが提供する他のサービスの案内のメールを送付するため' : 'To send emails regarding new features, update information, campaigns, etc., of the service the user is using and information on other services provided by the Shop'}</li>
              <li>{lang === 'ja' ? 'メンテナンス，重要なお知らせなど必要に応じたご連絡のため' : 'To contact users as necessary for maintenance, important notices, etc.'}</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-bold text-white mb-3">{t('第3条（個人情報の第三者提供）', lang)}</h2>
            <p>
              {lang === 'ja'
                ? '当ショップは，次に掲げる場合を除いて，あらかじめユーザーの同意を得ることなく，第三者に個人情報を提供することはありません。'
                : 'The Shop will not provide personal information to a third party without obtaining the user\'s prior consent, except in the following cases:'}
            </p>
            <ul className="list-disc ml-6 mt-2 space-y-1">
              <li>{lang === 'ja' ? '人の生命，身体または財産の保護のために必要がある場合であって，本人の同意を得ることが困難であるとき' : 'When it is necessary for the protection of human life, body, or property and it is difficult to obtain the consent of the individual'}</li>
              <li>{lang === 'ja' ? '公衆衛生の向上または児童の健全な育成の推進のために特に必要がある場合であって，本人の同意を得ることが困難であるとき' : 'When it is particularly necessary for the improvement of public health or the promotion of the healthy development of children and it is difficult to obtain the consent of the individual'}</li>
              <li>{lang === 'ja' ? '法令に基づく場合' : 'When required by law'}</li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  )
}
