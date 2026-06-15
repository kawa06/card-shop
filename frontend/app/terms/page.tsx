'use client'

import { ArrowLeft } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'

export default function TermsPage() {
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

        <h1 className="text-3xl font-bold text-white mb-8">利用規約</h1>

        <div className="bg-gray-900 rounded-xl border border-white/10 p-8 space-y-6 text-gray-300 leading-relaxed">
          <section>
            <h2 className="text-xl font-bold text-white mb-3">第1条（適用）</h2>
            <p>
              本規約は，ユーザーと当ショップ（以下，「当ショップ」といいます。）との間の本サービスの利用に関わる一切の関係に適用されるものとします。
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold text-white mb-3">第2条（利用登録）</h2>
            <p>
              登録希望者が当ショップの定める方法によって利用登録を申請し，当ショップがこれを承認することによって，利用登録が完了するものとします。
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold text-white mb-3">第3条（禁止事項）</h2>
            <p>ユーザーは，本サービスの利用にあたり，以下の行為をしてはなりません。</p>
            <ul className="list-disc ml-6 mt-2 space-y-1">
              <li>法令または公序良俗に違反する行為</li>
              <li>犯罪行為に関連する行為</li>
              <li>当ショップのサーバーまたはネットワークの機能を破壊したり，妨害したりする行為</li>
              <li>当ショップのサービスの運営を妨害するおそれのある行為</li>
              <li>他のユーザーに関する個人情報等を収集または蓄積する行為</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-bold text-white mb-3">第4条（免責事項）</h2>
            <p>
              当ショップの債務不履行責任は，当ショップの故意または重過失によらない場合には免責されるものとします。
            </p>
          </section>

          <section>
            <h2 className="text-xl font-bold text-white mb-3">第5条（準拠法・裁判管轄）</h2>
            <p>
              本規約の解釈にあたっては，日本法を準拠法とします。本サービスに関して紛争が生じた場合には，当ショップの本店所在地を管轄する裁判所を専属的合意管轄とします。
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
