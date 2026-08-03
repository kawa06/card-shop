'use client'

import {
  AdminBuybackConditionOption,
  AdminBuybackRejectionReasonOption,
  AdminBuybackRequestItem,
} from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export type ItemDraft = {
  line_status: string
  condition_code: string
  assessed_unit_price: string
  rejection_reason_code: string
  rejection_reason_text: string
  assessment_comment: string
  is_return_target: boolean
  is_disposal_target: boolean
}

export function itemToDraft(item: AdminBuybackRequestItem): ItemDraft {
  return {
    line_status: item.line_status || 'pending',
    condition_code: item.condition_code || 'default',
    assessed_unit_price:
      item.assessed_unit_price != null ? String(item.assessed_unit_price) : String(item.listed_unit_price),
    rejection_reason_code: item.rejection_reason_code || '',
    rejection_reason_text: item.rejection_reason_text || '',
    assessment_comment: item.assessment_comment || '',
    is_return_target: Boolean(item.is_return_target),
    is_disposal_target: Boolean(item.is_disposal_target),
  }
}

function formatYen(value: number | null): string {
  if (value == null) return '—'
  return `¥${value.toLocaleString('ja-JP')}`
}

function isBuying(status: string): boolean {
  return status === 'buyable' || status === 'reduced'
}

type Props = {
  items: AdminBuybackRequestItem[]
  drafts: Record<number, ItemDraft>
  canEdit: boolean
  reasonOptions: AdminBuybackRejectionReasonOption[]
  conditionOptions: AdminBuybackConditionOption[]
  onChange: (itemId: number, patch: Partial<ItemDraft>) => void
  onSave: () => void
  isSaving: boolean
}

export function BuybackAssessmentTable({
  items,
  drafts,
  canEdit,
  reasonOptions,
  conditionOptions,
  onChange,
  onSave,
  isSaving,
}: Props) {
  const setBuyDecision = (itemId: number, buy: boolean, listedPrice: number) => {
    if (buy) {
      onChange(itemId, {
        line_status: 'buyable',
        assessed_unit_price: String(listedPrice),
        rejection_reason_code: '',
      })
    } else {
      onChange(itemId, {
        line_status: 'rejected',
        assessed_unit_price: '',
      })
    }
  }

  const setPriceMode = (itemId: number, mode: 'full' | 'reduced', listedPrice: number, currentPrice: string) => {
    if (mode === 'full') {
      onChange(itemId, {
        line_status: 'buyable',
        assessed_unit_price: String(listedPrice),
      })
    } else {
      onChange(itemId, {
        line_status: 'reduced',
        assessed_unit_price: currentPrice || String(Math.max(0, listedPrice - 100)),
      })
    }
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="bg-gray-50 px-4 py-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="font-semibold">商品査定</h2>
          <p className="text-xs text-gray-500 mt-0.5">各商品について「買取する」「買取しない」を選択してください</p>
        </div>
        {canEdit && (
          <Button onClick={onSave} disabled={isSaving} size="sm">
            査定内容を保存
          </Button>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 border-t">
            <tr>
              <th className="px-3 py-2 text-left">商品</th>
              <th className="px-3 py-2 text-left">買取判定</th>
              <th className="px-3 py-2 text-left">状態</th>
              <th className="px-3 py-2 text-left">査定単価</th>
              <th className="px-3 py-2 text-left">理由</th>
              <th className="px-3 py-2 text-left">査定コメント</th>
              <th className="px-3 py-2 text-left">返送/処分</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const draft = drafts[item.id]
              if (!draft) return null
              const buying = isBuying(draft.line_status)
              const reasonLabel =
                draft.line_status === 'reduced'
                  ? '減額理由'
                  : draft.line_status === 'rejected'
                    ? '買取不可理由'
                    : '理由'

              return (
                <tr key={item.id} className="border-t align-top">
                  <td className="px-3 py-3 min-w-[180px]">
                    <div className="font-medium">{item.product_name_snapshot}</div>
                    <div className="text-gray-500 text-xs mt-1">
                      申込 {item.condition_code_label || item.condition_code} / 数量 {item.quantity} / 参考{' '}
                      {formatYen(item.listed_unit_price)}
                    </div>
                  </td>
                  <td className="px-3 py-3 min-w-[200px]">
                    {canEdit ? (
                      <div className="space-y-2">
                        <div className="flex gap-1">
                          <Button
                            type="button"
                            size="sm"
                            variant={buying ? 'default' : 'outline'}
                            className={buying ? 'bg-emerald-600 hover:bg-emerald-700' : ''}
                            onClick={() => setBuyDecision(item.id, true, item.listed_unit_price)}
                          >
                            買取する
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant={draft.line_status === 'rejected' ? 'destructive' : 'outline'}
                            onClick={() => setBuyDecision(item.id, false, item.listed_unit_price)}
                          >
                            買取しない
                          </Button>
                        </div>
                        {buying && (
                          <div className="flex gap-1">
                            <button
                              type="button"
                              className={`text-xs px-2 py-1 rounded border ${
                                draft.line_status === 'buyable'
                                  ? 'bg-yellow-100 border-yellow-400 font-medium'
                                  : 'border-gray-200'
                              }`}
                              onClick={() =>
                                setPriceMode(item.id, 'full', item.listed_unit_price, draft.assessed_unit_price)
                              }
                            >
                              満額
                            </button>
                            <button
                              type="button"
                              className={`text-xs px-2 py-1 rounded border ${
                                draft.line_status === 'reduced'
                                  ? 'bg-amber-100 border-amber-400 font-medium'
                                  : 'border-gray-200'
                              }`}
                              onClick={() =>
                                setPriceMode(item.id, 'reduced', item.listed_unit_price, draft.assessed_unit_price)
                              }
                            >
                              減額
                            </button>
                          </div>
                        )}
                      </div>
                    ) : (
                      <span>{item.line_status_label || draft.line_status}</span>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    {canEdit ? (
                      <select
                        className="border rounded-md px-2 py-1 text-sm w-full min-w-[100px]"
                        value={draft.condition_code}
                        onChange={(e) => onChange(item.id, { condition_code: e.target.value })}
                      >
                        {conditionOptions.map((opt) => (
                          <option key={opt.code} value={opt.code}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      item.condition_code_label || draft.condition_code
                    )}
                  </td>
                  <td className="px-3 py-3">
                    {canEdit && buying ? (
                      <Input
                        className="min-w-[100px]"
                        placeholder="円"
                        value={draft.assessed_unit_price}
                        onChange={(e) => onChange(item.id, { assessed_unit_price: e.target.value })}
                      />
                    ) : (
                      <span>{draft.assessed_unit_price ? formatYen(Number(draft.assessed_unit_price)) : '—'}</span>
                    )}
                  </td>
                  <td className="px-3 py-3 min-w-[200px]">
                    {(draft.line_status === 'reduced' || draft.line_status === 'rejected') && canEdit ? (
                      <div className="space-y-2">
                        <label className="text-xs text-gray-500">{reasonLabel}</label>
                        <select
                          className="border rounded-md px-2 py-1 text-sm w-full"
                          value={draft.rejection_reason_code}
                          onChange={(e) => onChange(item.id, { rejection_reason_code: e.target.value })}
                        >
                          <option value="">選択</option>
                          {reasonOptions.map((opt) => (
                            <option key={opt.code} value={opt.code}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                        <Input
                          placeholder="自由入力"
                          value={draft.rejection_reason_text}
                          onChange={(e) => onChange(item.id, { rejection_reason_text: e.target.value })}
                        />
                      </div>
                    ) : (
                      <span className="text-gray-400 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-3 py-3 min-w-[160px]">
                    {canEdit ? (
                      <textarea
                        className="w-full border rounded-md px-2 py-1 text-sm min-h-[72px]"
                        placeholder="お客様向けコメント（任意）"
                        value={draft.assessment_comment}
                        onChange={(e) => onChange(item.id, { assessment_comment: e.target.value })}
                      />
                    ) : (
                      draft.assessment_comment || '—'
                    )}
                  </td>
                  <td className="px-3 py-3">
                    {canEdit ? (
                      <div className="space-y-2">
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={draft.is_return_target}
                            onChange={(e) => onChange(item.id, { is_return_target: e.target.checked })}
                          />
                          返送
                        </label>
                        <label className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={draft.is_disposal_target}
                            onChange={(e) => onChange(item.id, { is_disposal_target: e.target.checked })}
                          />
                          処分
                        </label>
                      </div>
                    ) : (
                      <span className="text-xs text-gray-600">
                        {draft.is_return_target ? '返送 ' : ''}
                        {draft.is_disposal_target ? '処分' : ''}
                        {!draft.is_return_target && !draft.is_disposal_target ? '—' : ''}
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
