'use client'

import { ArrowLeft } from 'lucide-react'
import { useRouter } from 'next/navigation'

export default function PrivacyPage() {
  const router = useRouter()

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="container py-8 max-w-3xl">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-gray-400 hover:text-white mb-6 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          戻る
        </button>

        <h1 className="text-3xl font-bold text-white mb-8">プライバシーポリシー</h1>

        <div className="bg-gray-900 rounded-xl border border-white/10 p-8 space-y-6 text-gray-300 leading-relaxed">
          <p>
            当ショップは，本ウェブサイト上で提供するサービス（以下,「本サービス」といいます。）における，ユーザーの個人情報の取扱いについて，以下のとおりプライバシーポリシー（以下，「本ポリシー」といいます。）を定めます。
          </p>

          <section>
            <h2 className="text-xl font-bold text-white mb-3">第1条（個人情報の収集方法）</h2>
            <p>
              当ショップは，ユーザーが利用登録をする際に氏名，生年月日，住所，電話番号，メールアドレス，銀行口座番号，クレジットカード番号などの個人情報をお尋ねすることがあります。
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold text-white mb-3">第2条（個人情報を収集・利用する目的）</h2>
            <p>当ショップが個人情報を収集・利用する目的は，以下のとおりです。</p>
            <ul className="list-disc ml-6 mt-2 space-y-1">
              <li>当ショップサービスの提供・運営のため</li>
              <li>ユーザーからのお問い合わせに回答するため</li>
              <li>ユーザーが利用中のサービスの新機能，更新情報，キャンペーン等及び当ショップが提供する他のサービスの案内のメールを送付するため</li>
              <li>メンテナンス，重要なお知らせなど必要に応じたご連絡のため</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-bold text-white mb-3">第3条（個人情報の第三者提供）</h2>
            <p>
              当ショップは，次に掲げる場合を除いて，あらかじめユーザーの同意を得ることなく，第三者に個人情報を提供することはありません。
            </p>
            <ul className="list-disc ml-6 mt-2 space-y-1">
              <li>人の生命，身体または財産の保護のために必要がある場合であって，本人の同意を得ることが困難であるとき</li>
              <li>公衆衛生の向上または児童の健全な育成の推進のために特に必要がある場合であって，本人の同意を得ることが困難であるとき</li>
              <li>法令に基づく場合</li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  )
}
