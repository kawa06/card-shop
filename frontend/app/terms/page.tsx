'use client'

import { ArrowLeft } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import {
  TERMS_INTRO,
  TERMS_SECTIONS,
  TERMS_ENACTED,
  TERMS_REVISED,
} from '@/lib/legal/terms'

export default function TermsPage() {
  const router = useRouter()
  const { lang } = useLangStore()

  if (lang !== 'ja') {
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
          <h1 className="text-3xl font-bold text-gray-900 mb-8">{t('利用規約', lang)}</h1>
          <div className="bg-gray-50 rounded-xl border border-gray-200 p-8 text-gray-600 leading-relaxed">
            <p>
              The official Terms of Service are provided in Japanese. Please switch the language to
              Japanese (JP) to view the full text.
            </p>
          </div>
        </div>
      </div>
    )
  }

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

        <h1 className="text-3xl font-bold text-gray-900 mb-8">利用規約</h1>

        <div className="bg-gray-50 rounded-xl border border-gray-200 p-8 space-y-8 text-gray-600 leading-relaxed">
          <p>{TERMS_INTRO}</p>

          {TERMS_SECTIONS.map((section) => (
            <section key={section.title}>
              <h2 className="text-xl font-bold text-gray-900 mb-3">{section.title}</h2>
              {section.paragraphs.map((paragraph, i) => (
                <p key={i} className={i > 0 ? 'mt-3' : undefined}>
                  {paragraph}
                </p>
              ))}
              {section.list && (
                <ul className="list-disc ml-6 mt-3 space-y-1">
                  {section.list.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
              {section.paragraphsAfter?.map((paragraph, i) => (
                <p key={`after-${i}`} className="mt-3">
                  {paragraph}
                </p>
              ))}
            </section>
          ))}

          <div className="pt-4 border-t border-gray-200 text-sm text-gray-500 space-y-1">
            <p>制定日：{TERMS_ENACTED}</p>
            <p>最終改定日：{TERMS_REVISED}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
