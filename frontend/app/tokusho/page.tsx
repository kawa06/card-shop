'use client'

import { ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useLangStore } from '@/store/lang'
import { t } from '@/lib/i18n'
import {
  TOKUSHO_ENACTED,
  TOKUSHO_INFO_ROWS,
  TOKUSHO_REVISED,
  TOKUSHO_SECTIONS,
  TOKUSHO_SITE_URL,
} from '@/lib/legal/tokusho'

function InfoValue({ row }: { row: (typeof TOKUSHO_INFO_ROWS)[number] }) {
  const values = Array.isArray(row.value) ? row.value : [row.value]

  return (
    <div>
      {values.map((line, i) =>
        row.href && i === 0 ? (
          <Link
            key={i}
            href={row.href}
            className="text-sky-600 hover:text-sky-500 underline break-all"
            target={row.href.startsWith('http') ? '_blank' : undefined}
            rel={row.href.startsWith('http') ? 'noopener noreferrer' : undefined}
          >
            {line}
          </Link>
        ) : (
          <p key={i} className={i > 0 ? 'mt-1' : undefined}>
            {line}
          </p>
        )
      )}
      {row.href?.startsWith('http') && (
        <p className="mt-1 text-sm text-gray-500 break-all">{TOKUSHO_SITE_URL}</p>
      )}
      {row.note && <p className="mt-2 text-sm text-gray-500">{row.note}</p>}
    </div>
  )
}

export default function TokushoPage() {
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
          <h1 className="text-3xl font-bold text-gray-900 mb-8">
            {t('特定商取引法に基づく表記', lang)}
          </h1>
          <div className="bg-gray-50 rounded-xl border border-gray-200 p-8 text-gray-600 leading-relaxed">
            <p>
              The official Specified Commercial Transactions Act notation is provided in Japanese.
              Please switch the language to Japanese (JP) to view the full text.
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

        <h1 className="text-3xl font-bold text-gray-900 mb-8">特定商取引法に基づく表記</h1>

        <div className="bg-gray-50 rounded-xl border border-gray-200 p-8 space-y-8 text-gray-600 leading-relaxed">
          <dl className="divide-y divide-gray-200 border border-gray-200 rounded-lg overflow-hidden bg-white">
            {TOKUSHO_INFO_ROWS.map((row) => (
              <div key={row.label} className="grid sm:grid-cols-[11rem_1fr] gap-2 sm:gap-4 p-4">
                <dt className="font-semibold text-gray-900 shrink-0">{row.label}</dt>
                <dd>
                  <InfoValue row={row} />
                </dd>
              </div>
            ))}
          </dl>

          {TOKUSHO_SECTIONS.map((section) => (
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
              {section.listAfter && (
                <ul className="list-disc ml-6 mt-3 space-y-1">
                  {section.listAfter.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
              {section.closingParagraphs?.map((paragraph, i) => (
                <p key={`closing-${i}`} className="mt-3">
                  {paragraph}
                </p>
              ))}
            </section>
          ))}

          <div className="pt-4 border-t border-gray-200 text-sm text-gray-500 space-y-1">
            <p>制定日：{TOKUSHO_ENACTED}</p>
            <p>最終改定日：{TOKUSHO_REVISED}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
