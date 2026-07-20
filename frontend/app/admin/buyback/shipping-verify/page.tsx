'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Truck, Volume2, VolumeX } from 'lucide-react'
import { useAdminGuard } from '@/hooks/useAdminGuard'
import { useAdminPermissions } from '@/hooks/useAdminPermissions'
import { adminBuybackLogisticsApi } from '@/lib/api'
import type { AdminBuybackShipVerifyResult } from '@/lib/types'
import { BuybackBarcodeScanner } from '@/components/admin/buyback/BuybackBarcodeScanner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const SOUND_KEY = 'buyback_ship_sound'

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
    }, ok ? 120 : 320)
  } catch {
    /* ignore */
  }
}

function deviceInfo(): string {
  return [navigator.userAgent || '', `viewport:${window.innerWidth}x${window.innerHeight}`]
    .join(' | ')
    .slice(0, 240)
}

export default function AdminBuybackShippingVerifyPage() {
  const { isReady } = useAdminGuard()
  const { hasPermission } = useAdminPermissions()
  const [isMounted, setIsMounted] = useState(false)
  const [soundOn, setSoundOn] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [flash, setFlash] = useState<'ok' | 'err' | null>(null)
  const [result, setResult] = useState<AdminBuybackShipVerifyResult | null>(null)
  const [lastCode, setLastCode] = useState('')
  const [checklist, setChecklist] = useState<Record<string, boolean>>({})
  const [trackingNumber, setTrackingNumber] = useState('')

  useEffect(() => {
    setIsMounted(true)
    if (window.localStorage.getItem(SOUND_KEY) === '0') setSoundOn(false)
  }, [])

  const allChecked = useMemo(() => {
    const items = result?.checklist_items || []
    if (!items.length) return false
    return items.every((item) => checklist[item.code])
  }, [checklist, result])

  const signal = useCallback(
    (ok: boolean) => {
      setFlash(ok ? 'ok' : 'err')
      if (soundOn) playTone(ok)
      window.setTimeout(() => setFlash(null), 1000)
    },
    [soundOn]
  )

  const handleScan = useCallback(
    async (code: string) => {
      setScanning(true)
      setError(null)
      setLastCode(code)
      try {
        const res = await adminBuybackLogisticsApi.shipScan({
          code,
          device_info: deviceInfo(),
        })
        const data = res.data
        setResult(data)
        setTrackingNumber(data.tracking_number || '')
        const next: Record<string, boolean> = {}
        ;(data.checklist_items || []).forEach((item) => {
          next[item.code] = false
        })
        setChecklist(next)

        if (!data.found) {
          signal(false)
          setError(data.message || '該当する梱包が見つかりません')
          return
        }
        if (data.already_shipped) {
          signal(false)
          setError('発送済みです。二重発送はできません。')
          return
        }
        if (data.is_cancelled) {
          signal(false)
          setError('キャンセル済み申込です。発送できません。')
          return
        }
        signal(true)
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
    [signal]
  )

  const handleConfirm = async () => {
    if (!result?.package_id || !result.can_confirm || !allChecked) return
    setConfirming(true)
    setError(null)
    try {
      const res = await adminBuybackLogisticsApi.shipConfirm({
        package_id: result.package_id,
        checklist,
        scanned_code: lastCode || undefined,
        tracking_number: trackingNumber || undefined,
        device_info: deviceInfo(),
      })
      setResult(res.data)
      signal(true)
    } catch (err: unknown) {
      signal(false)
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        '発送確定に失敗しました'
      setError(String(msg))
    } finally {
      setConfirming(false)
    }
  }

  if (!isMounted || !isReady) return null

  if (!hasPermission('buyback.ship.read')) {
    return (
      <div className="min-h-screen bg-white">
        <div className="container py-8 max-w-3xl">
          <p className="text-red-600">発送前確認の権限がありません。</p>
          <Link href="/admin" className="text-sm text-yellow-600 hover:underline mt-4 inline-block">
            ダッシュボードへ戻る
          </Link>
        </div>
      </div>
    )
  }

  const addr = result?.destination_address

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
            <Truck className="h-6 w-6 text-sky-600" />
            <h1 className="text-2xl font-bold text-gray-900">発送前確認</h1>
          </div>
          <button
            type="button"
            onClick={() => {
              setSoundOn((v) => {
                const next = !v
                window.localStorage.setItem(SOUND_KEY, next ? '1' : '0')
                return next
              })
            }}
            className="inline-flex items-center gap-1 text-sm text-gray-600 border rounded-md px-3 py-1.5"
          >
            {soundOn ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
            効果音 {soundOn ? 'ON' : 'OFF'}
          </button>
        </div>

        <div className="border rounded-xl p-4 mb-4 bg-white shadow-sm">
          <BuybackBarcodeScanner
            onScan={handleScan}
            disabled={scanning || confirming}
            soundEnabled={soundOn}
          />
        </div>

        {error && (
          <div className="mb-4 rounded-lg border-2 border-red-500 bg-red-50 text-red-800 px-4 py-4 text-lg font-bold text-center">
            {error}
          </div>
        )}

        {result?.found && (
          <div className="space-y-4">
            {result.already_shipped && (
              <div className="rounded-xl border-4 border-red-600 bg-red-100 text-red-900 px-4 py-6 text-center">
                <p className="text-3xl font-black tracking-wide">発送済みです</p>
                <p className="mt-2 text-base">二重発送はできません</p>
              </div>
            )}

            <div className="border rounded-xl p-5 bg-white space-y-4">
              <div>
                <p className="text-sm text-gray-500">発送先氏名</p>
                <p className="text-4xl sm:text-5xl font-black leading-tight break-words">
                  {result.destination_name || '—'}
                </p>
              </div>

              {addr ? (
                <div>
                  <p className="text-sm text-gray-500">住所</p>
                  <p className="text-2xl sm:text-3xl font-bold leading-snug">
                    〒{addr.postal_code || '—'}
                  </p>
                  <p className="text-2xl sm:text-3xl font-bold leading-snug mt-1">
                    {[addr.region, addr.city].filter(Boolean).join('') || '—'}
                  </p>
                  <p className="text-2xl sm:text-3xl font-bold leading-snug mt-1">
                    {addr.address_line1 || '—'}
                  </p>
                  {addr.address_line2 && (
                    <p className="text-2xl sm:text-3xl font-bold leading-snug mt-1">
                      {addr.address_line2}
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-amber-700 text-sm">住所を表示する権限がありません</p>
              )}

              {result.destination_phone && (
                <div>
                  <p className="text-sm text-gray-500">電話番号</p>
                  <p className="text-3xl font-bold">{result.destination_phone}</p>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t">
                <div>
                  <p className="text-sm text-gray-500">配送方法</p>
                  <p className="text-xl font-semibold">{result.shipping_method || '—'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">発送希望時間帯</p>
                  <p className="text-3xl font-black text-sky-800">
                    {result.preferred_time_slot || '指定なし'}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">発送希望日</p>
                  <p className="text-xl font-semibold">{result.preferred_ship_date || '—'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">箱番号</p>
                  <p className="text-xl font-semibold">
                    {result.box_index}/{result.total_boxes}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">買取番号</p>
                  <p className="font-mono font-semibold">
                    {result.public_buyback_code || result.request_number || '—'}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">梱包ID</p>
                  <p className="font-mono text-sm">{result.package_code}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">追跡番号</p>
                  <p className="font-semibold">{result.tracking_number || '—'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">ステータス</p>
                  <p>{result.package_status_label || result.package_status}</p>
                </div>
              </div>
            </div>

            {(result.warnings || []).length > 0 && (
              <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3">
                <p className="font-semibold text-amber-900 mb-1">注意</p>
                <ul className="list-disc pl-5 text-sm text-amber-900 space-y-1">
                  {result.warnings!.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            {(result.items || []).length > 0 && (
              <div className="border rounded-xl p-4 bg-white">
                <h2 className="font-semibold mb-2">同梱物</h2>
                <ul className="text-sm divide-y">
                  {result.items!.map((item) => (
                    <li key={item.request_item_id} className="py-2 flex justify-between gap-2">
                      <span>{item.product_name || `明細#${item.request_item_id}`}</span>
                      <span className="text-gray-500">× {item.quantity}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {!result.already_shipped && hasPermission('buyback.ship.confirm') && (
              <div className="border rounded-xl p-4 bg-white space-y-3">
                <h2 className="font-semibold text-lg">発送前チェック</h2>
                <div className="space-y-2">
                  {(result.checklist_items || []).map((item) => (
                    <label
                      key={item.code}
                      className="flex items-start gap-3 text-base border rounded-md px-3 py-2"
                    >
                      <input
                        type="checkbox"
                        className="mt-1 h-5 w-5"
                        checked={Boolean(checklist[item.code])}
                        onChange={(e) =>
                          setChecklist((prev) => ({ ...prev, [item.code]: e.target.checked }))
                        }
                      />
                      <span>{item.label}</span>
                    </label>
                  ))}
                </div>
                <label className="text-sm block">
                  追跡番号（必要なら更新）
                  <Input
                    className="mt-1"
                    value={trackingNumber}
                    onChange={(e) => setTrackingNumber(e.target.value)}
                  />
                </label>
                <Button
                  className="w-full h-14 text-lg"
                  disabled={
                    confirming ||
                    !result.can_confirm ||
                    !allChecked ||
                    !result.address_complete
                  }
                  onClick={() => void handleConfirm()}
                >
                  {confirming ? '処理中…' : '発送確定'}
                </Button>
                {!allChecked && (
                  <p className="text-sm text-gray-500 text-center">
                    すべてのチェックが完了するまで発送確定できません
                  </p>
                )}
                {!result.address_complete && (
                  <p className="text-sm text-red-600 text-center">住所が不完全なため発送確定できません</p>
                )}
              </div>
            )}

            {result.request_id && (
              <Link
                href={`/admin/buyback/requests/${result.request_id}`}
                className="inline-block text-sm text-sky-700 hover:underline"
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
