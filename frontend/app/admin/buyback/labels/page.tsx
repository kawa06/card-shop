'use client'

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { ArrowLeft, Loader2, Printer } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminBuybackLogisticsApi } from '@/lib/api'
import type {
  AdminBuybackLabelLayout,
  AdminBuybackLabelSheetCell,
  AdminBuybackPackage,
} from '@/lib/types'
import { layoutCssVars, placeLabelsOnSheet } from '@/lib/buyback-label-yasan'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export default function AdminBuybackLabelsPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      }
    >
      <AdminBuybackLabelsContent />
    </Suspense>
  )
}

function AdminBuybackLabelsContent() {
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const searchParams = useSearchParams()
  const requestId = Number(searchParams.get('request_id') || 0) || null
  const presetIds = useMemo(() => {
    const raw = searchParams.get('package_ids') || ''
    return raw
      .split(',')
      .map((v) => Number(v.trim()))
      .filter((n) => Number.isFinite(n) && n > 0)
  }, [searchParams])

  const [isMounted, setIsMounted] = useState(false)
  const [layout, setLayout] = useState<AdminBuybackLabelLayout | null>(null)
  const [packages, setPackages] = useState<AdminBuybackPackage[]>([])
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [startPosition, setStartPosition] = useState(1)
  const [copies, setCopies] = useState(1)
  const [includeName, setIncludeName] = useState(false)
  const [sheetLabels, setSheetLabels] = useState<AdminBuybackLabelSheetCell[]>([])
  const [sheetStart, setSheetStart] = useState(1)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const canPrint = hasPermission('buyback.print.internal')
  const canName = hasPermission('admin.pii.read') && hasPermission('buyback.print.pii')
  const faces = layout?.faces || 65
  const cells = useMemo(
    () => placeLabelsOnSheet(sheetLabels, sheetStart, faces),
    [sheetLabels, sheetStart, faces]
  )

  const load = useCallback(async () => {
    setError(null)
    try {
      const layoutRes = await adminBuybackLogisticsApi.getLabelLayout()
      setLayout(layoutRes.data)
      if (requestId) {
        const pkgRes = await adminBuybackLogisticsApi.listPackages(requestId)
        setPackages(pkgRes.data)
        setSelected(new Set(presetIds.length > 0 ? presetIds : pkgRes.data.map((p) => p.id)))
      } else if (presetIds.length > 0) {
        setSelected(new Set(presetIds))
        setPackages(
          presetIds.map((id) => ({
            id,
            request_id: 0,
            package_code: `#${id}`,
            box_index: 1,
            total_boxes: 1,
            package_kind: 'return',
            status: 'unknown',
          }))
        )
      }
    } catch {
      setError('ラベル設定の取得に失敗しました')
    }
  }, [presetIds, requestId])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void load()
  }, [isMounted, isReady, load])

  const selectedIds = useMemo(() => Array.from(selected), [selected])

  const toggle = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleSheet = async () => {
    if (!selectedIds.length) {
      setError('印刷する梱包を選択してください')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const res = await adminBuybackLogisticsApi.getLabelSheet({
        package_ids: selectedIds,
        start_position: startPosition,
        copies,
        include_applicant_name: includeName && canName,
      })
      setLayout(res.data.layout)
      setSheetLabels(res.data.labels)
      setSheetStart(res.data.start_position)
    } catch {
      setError('シートデータの取得に失敗しました')
    } finally {
      setBusy(false)
    }
  }

  if (!isMounted || !isReady) return null

  if (!canPrint) {
    return (
      <div className="p-8">
        <p className="text-red-600">ラベル出力権限がありません。</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="no-print sticky top-0 z-10 bg-white border-b px-4 py-3">
        <div className="max-w-5xl mx-auto flex flex-wrap items-center justify-between gap-3">
          <Link
            href={requestId ? `/admin/buyback/requests/${requestId}` : '/admin/buyback/requests'}
            className="inline-flex items-center gap-1 text-sm text-gray-600"
          >
            <ArrowLeft className="h-4 w-4" />
            戻る
          </Link>
          <h1 className="text-lg font-semibold">ラベル屋さん / 72265</h1>
          <div className="flex gap-2">
            {canPrint && (
              <>
                <Button size="sm" variant="secondary" disabled={busy} onClick={() => void handleSheet()}>
                  シート準備
                </Button>
                <Button size="sm" disabled={!sheetLabels.length} onClick={() => window.print()}>
                  <Printer className="h-4 w-4 mr-1" />
                  印刷
                </Button>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="no-print max-w-5xl mx-auto p-4 space-y-4">
        {error && <p className="text-red-600 text-sm">{error}</p>}

        {layout && (
          <div className="rounded-lg border bg-white p-4 text-sm space-y-2">
            <p>
              品番 <span className="font-mono font-semibold">{layout.product_code}</span>
              （{layout.format_code}）· {layout.faces}面（{layout.columns}列×{layout.rows}段）· 一片{' '}
              {layout.label_width_mm}×{layout.label_height_mm}mm
            </p>
            {!layout.margins_confirmed && (
              <p className="text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
                {layout.margins_note}
              </p>
            )}
            <a
              href={layout.source_url}
              target="_blank"
              rel="noreferrer"
              className="text-sky-700 underline text-xs"
            >
              エーワン公式仕様
            </a>
          </div>
        )}

        <div className="rounded-lg border bg-white p-4 space-y-3">
          <div className="flex flex-wrap gap-4 text-sm">
            <label className="flex items-center gap-2">
              開始位置
              <Input
                type="number"
                min={1}
                max={faces}
                className="w-20"
                value={startPosition}
                onChange={(e) => setStartPosition(Number(e.target.value) || 1)}
              />
              <span className="text-gray-500">/ {faces}</span>
            </label>
            <label className="flex items-center gap-2">
              同一ラベル枚数
              <Input
                type="number"
                min={1}
                max={20}
                className="w-20"
                value={copies}
                onChange={(e) => setCopies(Number(e.target.value) || 1)}
              />
            </label>
            {canName && (
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={includeName}
                  onChange={(e) => setIncludeName(e.target.checked)}
                />
                申込者名を含める（住所・電話は出さない）
              </label>
            )}
          </div>

          {packages.length > 0 ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="py-2 w-10" />
                  <th className="py-2">梱包ID</th>
                  <th className="py-2">箱</th>
                  <th className="py-2">種別</th>
                </tr>
              </thead>
              <tbody>
                {packages.map((pkg) => (
                  <tr key={pkg.id} className="border-b">
                    <td className="py-2">
                      <input
                        type="checkbox"
                        checked={selected.has(pkg.id)}
                        onChange={() => toggle(pkg.id)}
                      />
                    </td>
                    <td className="py-2 font-mono">{pkg.package_code}</td>
                    <td className="py-2">
                      {pkg.box_index}/{pkg.total_boxes}
                    </td>
                    <td className="py-2">{pkg.package_kind_label || pkg.package_kind}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-gray-500">
              申込詳細の梱包一覧から開くか、
              <code className="mx-1">?request_id=</code>
              または
              <code className="mx-1">?package_ids=</code>
              を指定してください。
            </p>
          )}
        </div>
      </div>

      {layout && sheetLabels.length > 0 && (
        <div
          className="label-sheet mx-auto bg-white shadow print:shadow-none"
          style={layoutCssVars(layout) as React.CSSProperties}
        >
          {cells.map((cell, i) => (
            <div key={i} className="label-cell">
              {cell ? (
                <div className="label-inner">
                  <p className="shop">{cell.shop_name || layout.shop_name}</p>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`/api/admin/buyback/packages/${cell.package_id}/barcode.svg`}
                    alt="物流バーコード"
                    className="bc"
                  />
                  <p className="code">{cell.package_code}</p>
                  <p className="buy">{cell.public_buyback_code || cell.request_number || ''}</p>
                  {cell.applicant_name && <p className="name">{cell.applicant_name}</p>}
                  <p className="note">{cell.handling_note || '取扱注意'}</p>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}

      <style>{`
        .label-sheet {
          width: var(--sheet-w);
          height: var(--sheet-h);
          box-sizing: border-box;
          padding: var(--margin-t) var(--margin-l);
          display: grid;
          grid-template-columns: repeat(var(--cols), var(--label-w));
          grid-template-rows: repeat(var(--rows), var(--label-h));
          column-gap: var(--gap-h);
          row-gap: var(--gap-v);
          margin-top: 1rem;
          margin-bottom: 2rem;
        }
        .label-cell {
          width: var(--label-w);
          height: var(--label-h);
          overflow: hidden;
          box-sizing: border-box;
        }
        .label-inner {
          width: 100%;
          height: 100%;
          padding: 0.8mm 1mm;
          font-size: 5.5pt;
          line-height: 1.15;
          display: flex;
          flex-direction: column;
          justify-content: flex-start;
        }
        .label-inner .shop { font-weight: 700; font-size: 5pt; }
        .label-inner .bc { max-width: 100%; max-height: 8mm; }
        .label-inner .code {
          font-family: ui-monospace, monospace;
          font-size: 5pt;
          word-break: break-all;
        }
        .label-inner .buy,
        .label-inner .name,
        .label-inner .note { font-size: 5pt; }
        .label-inner .note { font-weight: 700; }
        @media print {
          .no-print { display: none !important; }
          body { margin: 0; background: white; }
          .label-sheet { margin: 0; box-shadow: none; page-break-after: always; }
          @page { size: A4; margin: 0; }
        }
      `}</style>
    </div>
  )
}
