'use client'

import Link from 'next/link'
import { AdminBuybackRequestDetail } from '@/lib/types'

type Props = {
  detail: AdminBuybackRequestDetail
}

export function BuybackMailWorkflowPanel({ detail }: Props) {
  return (
    <div className="border rounded-lg p-4 space-y-3 bg-sky-50/40 border-sky-200">
      <h2 className="font-semibold text-sky-900">郵送買取ワークフロー</h2>
      <p className="text-sm text-gray-600">
        荷物の受付・査定・返送は郵送専用フローで管理します。ステータスに応じて以下の操作を行ってください。
      </p>
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/admin/buyback/receiving" className="text-amber-700 hover:underline font-medium">
          荷物受付（バーコードスキャン）
        </Link>
        <Link href="/admin/buyback/shipping-verify" className="text-sky-700 hover:underline font-medium">
          発送前確認
        </Link>
        <Link href={`/admin/buyback/labels?request_id=${detail.id}`} className="text-teal-700 hover:underline font-medium">
          返送ラベル印刷
        </Link>
      </div>
      {detail.tracking_number && (
        <p className="text-sm">
          <span className="text-gray-500">お客様追跡番号：</span>
          {detail.tracking_number}
        </p>
      )}
      <ul className="text-xs text-gray-500 list-disc pl-5 space-y-1">
        <li>受付後：ステータスを「査定中」に更新し、商品査定を入力</li>
        <li>査定完了：「査定結果を提示」でお客様に通知</li>
        <li>返送が必要な場合：梱包バーコードを発行</li>
      </ul>
    </div>
  )
}
