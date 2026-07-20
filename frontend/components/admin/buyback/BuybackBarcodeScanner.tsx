'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Camera, ScanLine, Volume2, VolumeX, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface BuybackBarcodeScannerProps {
  onScan: (code: string) => void
  disabled?: boolean
  soundEnabled?: boolean
}

declare global {
  interface Window {
    BarcodeDetector?: new (options?: { formats?: string[] }) => {
      detect: (source: ImageBitmapSource) => Promise<Array<{ rawValue: string }>>
    }
  }
}

function CameraPanel({
  onScan,
  onClose,
}: {
  onScan: (code: string) => void
  onClose: () => void
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(true)
  const activeRef = useRef(true)

  useEffect(() => {
    activeRef.current = true
    let raf = 0
    let detector: InstanceType<NonNullable<typeof window.BarcodeDetector>> | null = null

    const stop = () => {
      activeRef.current = false
      if (raf) cancelAnimationFrame(raf)
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }

    const loop = async () => {
      if (!activeRef.current || !videoRef.current || !detector) return
      try {
        if (videoRef.current.readyState >= 2) {
          const codes = await detector.detect(videoRef.current)
          if (codes.length > 0 && codes[0].rawValue) {
            const value = codes[0].rawValue.trim()
            if (value) {
              stop()
              onScan(value)
              onClose()
              return
            }
          }
        }
      } catch {
        /* keep scanning */
      }
      raf = requestAnimationFrame(() => {
        void loop()
      })
    }

    const start = async () => {
      if (!window.BarcodeDetector) {
        setError(
          'このブラウザはカメラ読取に対応していません。USBリーダーまたは手入力を利用してください。'
        )
        setStarting(false)
        return
      }
      try {
        detector = new window.BarcodeDetector({
          formats: ['code_128', 'qr_code', 'ean_13', 'code_39'],
        })
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' } },
          audio: false,
        })
        if (!activeRef.current) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          await videoRef.current.play()
        }
        setStarting(false)
        void loop()
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'カメラを起動できませんでした。ブラウザのカメラ許可を確認してください。'
        )
        setStarting(false)
      }
    }

    void start()
    return stop
  }, [onClose, onScan])

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl w-full max-w-md overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <p className="font-medium">カメラで読取</p>
          <button type="button" onClick={onClose} className="text-gray-500 hover:text-gray-900">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="relative bg-black aspect-[3/4]">
          <video ref={videoRef} className="w-full h-full object-cover" muted playsInline />
          {starting && !error && (
            <p className="absolute inset-0 flex items-center justify-center text-white text-sm">
              カメラ起動中…
            </p>
          )}
          {error && (
            <p className="absolute inset-0 flex items-center justify-center text-red-200 text-sm p-4 text-center">
              {error}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export function BuybackBarcodeScanner({
  onScan,
  disabled,
  soundEnabled = true,
}: BuybackBarcodeScannerProps) {
  const [value, setValue] = useState('')
  const [showCamera, setShowCamera] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const firstKeyTimeRef = useRef(0)
  const debounceRef = useRef<number | null>(null)

  const submit = useCallback(
    (code: string) => {
      const trimmed = code.trim()
      if (!trimmed || disabled) return
      onScan(trimmed)
      setValue('')
      firstKeyTimeRef.current = 0
      window.setTimeout(() => inputRef.current?.focus(), 0)
    },
    [disabled, onScan]
  )

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current)
    }
  }, [])

  return (
    <>
      <form
        className="flex flex-col sm:flex-row gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          submit(value)
        }}
      >
        <div className="relative flex-1">
          <ScanLine className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            ref={inputRef}
            value={value}
            disabled={disabled}
            placeholder="バーコードをスキャンまたは手入力..."
            className="pl-9 text-base h-12"
            autoComplete="off"
            onChange={(e) => {
              const next = e.target.value
              const now = Date.now()
              if (!firstKeyTimeRef.current || now - firstKeyTimeRef.current > 400) {
                firstKeyTimeRef.current = now
              }
              setValue(next)
              if (debounceRef.current) window.clearTimeout(debounceRef.current)
              debounceRef.current = window.setTimeout(() => {
                const elapsed = Date.now() - firstKeyTimeRef.current
                if (next.trim() && elapsed < 350) submit(next)
              }, 120)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                if (debounceRef.current) window.clearTimeout(debounceRef.current)
                submit(value)
              }
            }}
          />
        </div>
        <div className="flex gap-2">
          <Button type="submit" disabled={disabled || !value.trim()} className="h-12">
            読取
          </Button>
          <Button
            type="button"
            variant="outline"
            className="h-12"
            disabled={disabled}
            onClick={() => setShowCamera(true)}
          >
            <Camera className="h-4 w-4 mr-1" />
            カメラ
          </Button>
        </div>
      </form>
      <p className="text-xs text-gray-500 mt-2 flex items-center gap-1">
        {soundEnabled ? <Volume2 className="h-3.5 w-3.5" /> : <VolumeX className="h-3.5 w-3.5" />}
        USB / Bluetooth リーダー対応 · 手入力可 · 連続読取可能
      </p>
      {showCamera && (
        <CameraPanel
          onScan={submit}
          onClose={() => {
            setShowCamera(false)
            window.setTimeout(() => inputRef.current?.focus(), 100)
          }}
        />
      )}
    </>
  )
}
