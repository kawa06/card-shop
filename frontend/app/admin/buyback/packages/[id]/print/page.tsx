'use client'

import { Suspense, useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams, useSearchParams } from 'next/navigation'
import { ArrowLeft, Loader2, Printer } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminBuybackLogisticsApi } from '@/lib/api'
import type { AdminBuybackPackageLabel } from '@/lib/types'
import { Button } from '@/components/ui/button'

export default function AdminPackageLabelPrintPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      }
    >
      <AdminPackageLabelPrintContent />
    </Suspense>
  )
}

function AdminPackageLabelPrintContent() {
  const params = useParams()
  const searchParams = useSearchParams()
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const packageId = Number(params.id)
  const [label, setLabel] = useState<AdminBuybackPackageLabel | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isMounted, setIsMounted] = useState(false)
  const showReprint = searchParams.get('reprint') === '1'

  useEffect(() => {
    setIsMounted(true)
  }, [])

  const load = useCallback(async () => {
    if (!packageId) return
    setError(null)
    try {
      const res = await adminBuybackLogisticsApi.printPackageLabel(packageId, {
        is_reprint: showReprint,
        device_info: navigator.userAgent.slice(0, 240),
      })
      setLabel(res.data)
    } catch {
      try {
        const res = await adminBuybackLogisticsApi.getPackageLabel(packageId)
        setLabel(res.data)
      } catch {
        setError('ラベルデータの取得に失敗しました')
      }
    }
  }, [packageId, showReprint])

  useEffect(() => {
    if (!isMounted || !isReady) return
    void load()
  }, [isMounted, isReady, load])

  if (!isMounted || !isReady) return null

  if (!hasPermission('buyback.print.internal')) {
    return (
      <div className="p-8">
        <p className="text-red-600">印刷権限がありません。</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="no-print sticky top-0 z-10 bg-white border-b px-4 py-3 flex items-center justify-between gap-3">
        <Link
          href={label ? `/admin/buyback/requests/${label.request_id}` : '/admin/buyback/requests'}
          className="inline-flex items-center gap-1 text-sm text-gray-600"
        >
          <ArrowLeft className="h-4 w-4" />
          申込詳細へ
        </Link>
        <Button onClick={() => window.print()} size="sm">
          <Printer className="h-4 w-4 mr-1" />
          印刷
        </Button>
      </div>

      {error && <p className="p-4 text-red-600">{error}</p>}

      {label && (
        <div className="print-sheet mx-auto my-6 bg-white p-8 max-w-[180mm] shadow print:shadow-none print:m-0 print:max-w-none">
          <div className="flex justify-between gap-4 border-b-2 border-black pb-3 mb-4">
            <div>
              <p className="text-xl font-bold tracking-wide">{label.shop_name}</p>
              <h1 className="text-2xl font-bold mt-1">梱包ラベル</h1>
              <p className="text-sm text-gray-600 mt-1">
                {label.package_kind_label} · 箱 {label.box_index}/{label.total_boxes}
              </p>
              {(label.is_reprint || showReprint) && (
                <p className="inline-block mt-2 border-2 border-red-600 text-red-600 font-bold px-2 py-0.5 text-sm">
                  再印刷
                </p>
              )}
            </div>
            <div className="text-center min-w-[140px]">
              {/* The server renders the bearer credential directly into bars. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`/api/admin/buyback/packages/${label.id}/barcode.svg`}
                alt="物流バーコード"
                className="mx-auto h-[64px] max-w-full"
              />
              <p className="text-[10px] font-mono mt-1 break-all">
                {label.barcode_human_readable || label.package_code}
              </p>
            </div>
          </div>

          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm mb-4">
            <div>
              <dt className="text-gray-500">買取番号</dt>
              <dd className="font-semibold text-lg">
                {label.public_buyback_code || label.request_number || '—'}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">梱包ID</dt>
              <dd className="font-mono">{label.package_code}</dd>
            </div>
            <div>
              <dt className="text-gray-500">荷物管理ID</dt>
              <dd className="font-mono">{label.inbound_mgmt_id || '—'}</dd>
            </div>
            <div>
              <dt className="text-gray-500">申込者</dt>
              <dd className="font-bold text-lg">{label.applicant_name || '—'}</dd>
            </div>
            <div>
              <dt className="text-gray-500">商品点数</dt>
              <dd>{label.item_count} 点</dd>
            </div>
            <div>
              <dt className="text-gray-500">配送方法</dt>
              <dd>{label.shipping_method || '—'}</dd>
            </div>
            <div>
              <dt className="text-gray-500">希望日</dt>
              <dd>{label.preferred_ship_date || '—'}</dd>
            </div>
            <div>
              <dt className="text-gray-500">希望時間帯</dt>
              <dd className="font-semibold">{label.preferred_time_slot || '—'}</dd>
            </div>
            <div>
              <dt className="text-gray-500">追跡番号</dt>
              <dd>{label.tracking_number || '—'}</dd>
            </div>
            <div>
              <dt className="text-gray-500">ステータス</dt>
              <dd>{label.status_label || label.status}</dd>
            </div>
          </dl>

          <p className="border border-black text-center font-bold py-2 mb-4">{label.handling_note}</p>

          {(label.items || []).length > 0 && (
            <div className="text-sm mb-4">
              <p className="font-semibold mb-1">同梱（登録）</p>
              <ul className="list-disc pl-5">
                {label.items!.map((item) => (
                  <li key={item.request_item_id}>
                    {item.product_name || `明細#${item.request_item_id}`} × {item.quantity}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="text-xs text-gray-500 border-t pt-2">
            倉庫内ラベル用途。住所・電話は権限がある場合のみ表示されます。
            {label.destination_phone ? ` 電話: ${label.destination_phone}` : ''}
          </p>
        </div>
      )}

      <style>{`
        @media print {
          @page { size: A4 portrait; margin: 10mm; }
          .no-print { display: none !important; }
          body { background: white !important; }
        }
      `}</style>
    </div>
  )
}
