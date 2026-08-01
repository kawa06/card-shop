'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, PackageCheck, Volume2, VolumeX } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminBuybackLogisticsApi } from '@/lib/api'
import type { AdminBuybackScanResult } from '@/lib/types'
import { BuybackBarcodeScanner } from '@/components/admin/buyback/BuybackBarcodeScanner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const SOUND_KEY = 'buyback_receive_sound'

function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('ja-JP')
}

function playTone(ok: boolean) {
  try {
    const ctx = new AudioContext()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.frequency.value = ok ? 880 : 220
    gain.gain.value = 0.08
    osc.start()
    window.setTimeout(() => {
      osc.stop()
      void ctx.close()
    }, ok ? 120 : 280)
  } catch {
    /* ignore */
  }
}

function deviceInfo(): string {
  return [navigator.userAgent || '', `viewport:${window.innerWidth}x${window.innerHeight}`]
    .join(' | ')
    .slice(0, 240)
}

export default function AdminBuybackReceivingPage() {
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const [isMounted, setIsMounted] = useState(false)
  const [soundOn, setSoundOn] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [receiving, setReceiving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [flash, setFlash] = useState<'ok' | 'err' | null>(null)
  const [result, setResult] = useState<AdminBuybackScanResult | null>(null)
  const [awaitingConfirmScan, setAwaitingConfirmScan] = useState(false)
  const [boxCount, setBoxCount] = useState('1')
  const [actualCount, setActualCount] = useState('')
  const [conditionNote, setConditionNote] = useState('')
  const [adminNote, setAdminNote] = useState('')

  useEffect(() => {
    setIsMounted(true)
    const saved = window.localStorage.getItem(SOUND_KEY)
    if (saved === '0') setSoundOn(false)
  }, [])

  const toggleSound = () => {
    setSoundOn((prev) => {
      const next = !prev
      window.localStorage.setItem(SOUND_KEY, next ? '1' : '0')
      return next
    })
  }

  const signal = useCallback(
    (ok: boolean) => {
      setFlash(ok ? 'ok' : 'err')
      if (soundOn) playTone(ok)
      window.setTimeout(() => setFlash(null), 900)
    },
    [soundOn]
  )

  const performReceive = useCallback(
    async (code: string) => {
      if (!result?.inbound_shipment_id || !result.can_receive) return
      setReceiving(true)
      setError(null)
      try {
        const res = await adminBuybackLogisticsApi.receive({
          inbound_shipment_id: result.inbound_shipment_id,
          scanned_code: code,
          box_count: Number(boxCount) || 1,
          actual_item_count: actualCount ? Number(actualCount) : undefined,
          condition_note: conditionNote || undefined,
          admin_note: adminNote || undefined,
          device_info: deviceInfo(),
        })
        setResult(res.data)
        signal(true)
      } catch (err: unknown) {
        signal(false)
        const msg =
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          '受付に失敗しました'
        setError(String(msg))
      } finally {
        setReceiving(false)
        setAwaitingConfirmScan(false)
      }
    },
    [actualCount, adminNote, boxCount, conditionNote, result, signal]
  )

  const handleScan = useCallback(
    async (code: string) => {
      if (awaitingConfirmScan) {
        await performReceive(code)
        return
      }
      setScanning(true)
      setError(null)
      try {
        const res = await adminBuybackLogisticsApi.scan({
          code,
          device_info: deviceInfo(),
        })
        const data = res.data
        setResult(data)
        if (!data.found) {
          signal(false)
          setError(data.message || '該当する申込が見つかりません')
          return
        }
        if (data.is_cancelled) {
          signal(false)
          setError('この申込はキャンセル済みです')
          return
        }
        signal(true)
        setActualCount(
          data.declared_item_count != null ? String(data.declared_item_count) : ''
        )
        setBoxCount(String(data.expected_box_count || 1))
      } catch (err: unknown) {
        signal(false)
        const msg =
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          '読取に失敗しました'
        setError(String(msg))
        setResult(null)
      } finally {
        setScanning(false)
      }
    },
    [awaitingConfirmScan, performReceive, signal]
  )

  const handleReceive = () => {
    if (!result?.inbound_shipment_id || !result.can_receive) return
    setError('到着確定のため、同じバーコードをもう一度スキャンしてください')
    setAwaitingConfirmScan(true)
  }

  if (!isMounted || !isReady) return null

  if (!hasPermission('buyback.receive')) {
    return (
      <div className="min-h-screen bg-white">
        <div className="container py-8 max-w-3xl">
          <p className="text-red-600">荷物受付の権限がありません。</p>
          <Link href="/admin" className="text-sm text-yellow-600 hover:underline mt-4 inline-block">
            ダッシュボードへ戻る
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div
      className={`min-h-screen transition-colors ${
        flash === 'ok' ? 'bg-emerald-50' : flash === 'err' ? 'bg-red-50' : 'bg-white'
      }`}
    >
      <div className="container py-6 max-w-3xl">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
          <div className="flex items-center gap-3">
            <Link href="/admin/buyback/requests" className="text-gray-500 hover:text-gray-900">
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <PackageCheck className="h-6 w-6 text-amber-500" />
            <h1 className="text-2xl font-bold text-gray-900">買取荷物受付</h1>
          </div>
          <button
            type="button"
            onClick={toggleSound}
            className="inline-flex items-center gap-1 text-sm text-gray-600 border rounded-md px-3 py-1.5"
          >
            {soundOn ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
            効果音 {soundOn ? 'ON' : 'OFF'}
          </button>
        </div>

        <div className="border rounded-xl p-4 mb-4 bg-white shadow-sm">
          <BuybackBarcodeScanner onScan={handleScan} disabled={scanning || receiving} soundEnabled={soundOn} />
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-red-300 bg-red-50 text-red-800 px-4 py-3 text-sm font-medium">
            {error}
          </div>
        )}

        {result?.found && (
          <div className="space-y-4">
            {result.already_received && (
              <div className="rounded-lg border border-amber-300 bg-amber-50 text-amber-900 px-4 py-3 text-sm font-medium">
                この荷物は既に受付済みです。内容を確認できます。
              </div>
            )}

            <div className="border rounded-xl p-4 bg-white">
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <div>
                  <dt className="text-gray-500">買取番号</dt>
                  <dd className="font-semibold text-lg">
                    {result.public_buyback_code || result.request_number || '—'}
                  </dd>
                </div>
                <div>
                  <dt className="text-gray-500">荷物管理ID</dt>
                  <dd className="font-mono">{result.inbound_mgmt_id || '—'}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">申込者氏名</dt>
                  <dd className="text-xl font-bold">{result.applicant_name || '—'}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">申込日時</dt>
                  <dd>{formatDate(result.submitted_at)}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">買取ステータス</dt>
                  <dd>{result.request_status_label || result.request_status}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">荷物状況</dt>
                  <dd>{result.inbound_status_label || result.inbound_status}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">申告点数</dt>
                  <dd className="font-semibold">{result.declared_item_count ?? '—'} 点</dd>
                </div>
                <div>
                  <dt className="text-gray-500">発送方法</dt>
                  <dd>{result.shipping_method || '—'}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">本人確認</dt>
                  <dd>{result.identity_status_label || '—'}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">未成年者同意</dt>
                  <dd>{result.guardian_status_label || '対象外 / 未設定'}</dd>
                </div>
                {result.user_email && (
                  <div>
                    <dt className="text-gray-500">メール</dt>
                    <dd>{result.user_email}</dd>
                  </div>
                )}
                {result.phone_number && (
                  <div>
                    <dt className="text-gray-500">電話</dt>
                    <dd>{result.phone_number}</dd>
                  </div>
                )}
              </dl>

              {result.admin_note || result.logistics_note ? (
                <div className="mt-3 text-sm">
                  <p className="text-gray-500">管理者メモ</p>
                  <p>{result.logistics_note || result.admin_note}</p>
                </div>
              ) : null}
            </div>

            <div className="border rounded-xl p-4 bg-white">
              <h2 className="font-semibold mb-2">申告商品一覧</h2>
              <ul className="divide-y text-sm">
                {(result.items || []).map((item) => (
                  <li key={item.id} className="py-2 flex justify-between gap-3">
                    <span>{item.product_name}</span>
                    <span className="text-gray-500 whitespace-nowrap">
                      {item.condition_code} × {item.quantity}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="border rounded-xl p-4 bg-white">
              <h2 className="font-semibold mb-2">注意事項</h2>
              <ul className="list-disc pl-5 text-sm text-gray-700 space-y-1">
                {(result.notices || []).map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            </div>

            {result.can_receive && (
              <div className="border rounded-xl p-4 bg-white space-y-3">
                <h2 className="font-semibold">荷物を受け付ける</h2>
                <div className="grid grid-cols-2 gap-3">
                  <label className="text-sm">
                    箱数
                    <Input
                      type="number"
                      min={1}
                      value={boxCount}
                      onChange={(e) => setBoxCount(e.target.value)}
                      className="mt-1"
                    />
                  </label>
                  <label className="text-sm">
                    実際の到着点数
                    <Input
                      type="number"
                      min={0}
                      value={actualCount}
                      onChange={(e) => setActualCount(e.target.value)}
                      className="mt-1"
                    />
                  </label>
                </div>
                <label className="text-sm block">
                  荷物の状態
                  <Input
                    value={conditionNote}
                    onChange={(e) => setConditionNote(e.target.value)}
                    className="mt-1"
                    placeholder="箱の破損など"
                  />
                </label>
                <label className="text-sm block">
                  管理者メモ
                  <Input
                    value={adminNote}
                    onChange={(e) => setAdminNote(e.target.value)}
                    className="mt-1"
                  />
                </label>
                <Button
                  className="w-full h-12 text-base"
                  onClick={() => void handleReceive()}
                  disabled={receiving || awaitingConfirmScan}
                >
                  {receiving
                    ? '処理中…'
                    : awaitingConfirmScan
                      ? '確定用バーコードを待機中…'
                      : '荷物を受け付ける'}
                </Button>
              </div>
            )}

            {(result.status_history || []).length > 0 && (
              <div className="border rounded-xl p-4 bg-white">
                <h2 className="font-semibold mb-2">操作履歴</h2>
                <ul className="text-sm space-y-2">
                  {(result.status_history || []).map((h) => (
                    <li key={h.id} className="border-b pb-2 last:border-0">
                      <p>
                        {h.from_status_label || '—'} → {h.to_status_label}
                      </p>
                      <p className="text-gray-500 text-xs">
                        {formatDate(h.created_at)}
                        {h.note ? ` · ${h.note}` : ''}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {(result.receipts || []).length > 0 && (
              <div className="border rounded-xl p-4 bg-white">
                <h2 className="font-semibold mb-2">受付記録</h2>
                <ul className="text-sm space-y-2">
                  {(result.receipts || []).map((r) => (
                    <li key={r.id} className="border-b pb-2 last:border-0">
                      <p>
                        {formatDate(r.received_at)} · {r.received_by_name || '担当者'}
                      </p>
                      <p className="text-gray-500 text-xs">
                        箱数 {r.box_count ?? '—'} / 点数 {r.actual_item_count ?? '—'}
                        {r.admin_note ? ` · ${r.admin_note}` : ''}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.request_id && (
              <Link
                href={`/admin/buyback/requests/${result.request_id}`}
                className="inline-block text-sm text-amber-700 hover:underline"
              >
                申込詳細を開く →
              </Link>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
