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

interface BarcodeDetectorInstance {
  detect: (source: ImageBitmapSource) => Promise<Array<{ rawValue: string }>>
}

interface BarcodeDetectorConstructor {
  new (options?: { formats?: string[] }): BarcodeDetectorInstance
  getSupportedFormats?: () => Promise<string[]>
}

declare global {
  interface Window {
    BarcodeDetector?: BarcodeDetectorConstructor
  }
}

const CAMERA_ERRORS = {
  insecure:
    '安全な接続（HTTPS）でないためカメラを利用できません。USBリーダーまたは手入力を利用してください。',
  permission:
    'カメラの使用が許可されていません。ブラウザの設定でカメラを許可してください。',
  notFound: '利用可能なカメラが見つかりません。USBリーダーまたは手入力を利用してください。',
  busy: 'カメラを起動できません。ほかのアプリで使用中でないか確認してください。',
  decoder:
    'このブラウザはバーコード解析に対応していません。USBリーダーまたは手入力を利用してください。',
  unsupported:
    'このブラウザはカメラの起動に対応していません。USBリーダーまたは手入力を利用してください。',
  start: 'カメラを起動できませんでした。ブラウザのカメラ設定を確認してください。',
  invalidBarcode: 'バーコードの読取結果が不正です。もう一度読み取ってください。',
} as const

const AUTO_SUBMIT_TOKEN = /^[A-Za-z0-9_-]{43}$/
const DETECTION_INTERVAL_MS = 250

function cameraStartError(error: unknown): string {
  if (!(error instanceof DOMException)) return CAMERA_ERRORS.start

  switch (error.name) {
    case 'NotAllowedError':
    case 'SecurityError':
      return CAMERA_ERRORS.permission
    case 'NotFoundError':
    case 'DevicesNotFoundError':
      return CAMERA_ERRORS.notFound
    case 'NotReadableError':
    case 'TrackStartError':
      return CAMERA_ERRORS.busy
    default:
      return CAMERA_ERRORS.start
  }
}

function isFacingModeConstraintFailure(error: unknown): boolean {
  if (!(error instanceof DOMException)) return false
  if (error.name !== 'OverconstrainedError' && error.name !== 'ConstraintNotSatisfiedError') {
    return false
  }

  const constraint = (error as DOMException & { constraint?: string }).constraint
  return !constraint || constraint === 'facingMode'
}

function CameraPanel({
  onScan,
  onClose,
}: {
  onScan: (code: string) => void
  onClose: () => void
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(true)
  const generationRef = useRef(0)
  const onScanRef = useRef(onScan)
  const onCloseRef = useRef(onClose)

  useEffect(() => {
    onScanRef.current = onScan
    onCloseRef.current = onClose
  }, [onClose, onScan])

  useEffect(() => {
    const generation = ++generationRef.current
    let cancelled = false
    let finished = false
    let raf: number | null = null
    let stream: MediaStream | null = null
    let detector: BarcodeDetectorInstance | null = null
    let detectionInFlight = false
    let lastDetectionAt = 0

    const isCurrent = () => !cancelled && generationRef.current === generation

    const releaseMedia = (extraStream?: MediaStream) => {
      if (raf !== null) {
        cancelAnimationFrame(raf)
        raf = null
      }
      const currentStream = stream
      stream = null
      currentStream?.getTracks().forEach((track) => track.stop())
      if (extraStream && extraStream !== currentStream) {
        extraStream.getTracks().forEach((track) => track.stop())
      }
      const video = videoRef.current
      if (video) {
        video.pause()
        video.srcObject = null
      }
    }

    const fail = (message: string, extraStream?: MediaStream) => {
      finished = true
      releaseMedia(extraStream)
      if (!isCurrent()) return
      setError(message)
      setStarting(false)
    }

    const scheduleDetection = () => {
      if (!isCurrent() || finished) return
      raf = requestAnimationFrame(detect)
    }

    const detect = async (timestamp: number) => {
      raf = null
      const video = videoRef.current
      if (!isCurrent() || finished || !video || !detector) return
      if (
        detectionInFlight ||
        video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA ||
        timestamp - lastDetectionAt < DETECTION_INTERVAL_MS
      ) {
        scheduleDetection()
        return
      }

      detectionInFlight = true
      lastDetectionAt = timestamp
      try {
        const codes = await detector.detect(video)
        if (!isCurrent() || finished) return
        if (!Array.isArray(codes)) {
          fail(CAMERA_ERRORS.invalidBarcode)
          return
        }
        if (codes.length > 0) {
          const rawValue = codes[0]?.rawValue
          if (typeof rawValue !== 'string') {
            fail(CAMERA_ERRORS.invalidBarcode)
            return
          }
          const value = rawValue.trim()
          if (value) {
            finished = true
            releaseMedia()
            onScanRef.current(value)
            onCloseRef.current()
            return
          }
        }
      } catch {
        /* keep scanning */
      } finally {
        detectionInFlight = false
      }
      scheduleDetection()
    }

    const start = async () => {
      if (!window.isSecureContext) {
        fail(CAMERA_ERRORS.insecure)
        return
      }
      if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== 'function') {
        fail(CAMERA_ERRORS.unsupported)
        return
      }

      let acquiredStream: MediaStream
      try {
        acquiredStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { exact: 'environment' } },
          audio: false,
        })
      } catch (firstError) {
        if (!isFacingModeConstraintFailure(firstError)) {
          fail(cameraStartError(firstError))
          return
        }

        try {
          acquiredStream = await navigator.mediaDevices.getUserMedia({
            video: true,
            audio: false,
          })
        } catch (retryError) {
          fail(cameraStartError(retryError))
          return
        }
      }

      if (!isCurrent()) {
        releaseMedia(acquiredStream)
        return
      }
      stream = acquiredStream

      const Detector = window.BarcodeDetector
      if (!Detector) {
        fail(CAMERA_ERRORS.decoder)
        return
      }

      try {
        if (Detector.getSupportedFormats) {
          const formats = await Detector.getSupportedFormats()
          if (!isCurrent()) {
            releaseMedia()
            return
          }
          if (!formats.includes('code_128')) {
            fail(CAMERA_ERRORS.decoder)
            return
          }
        }
        detector = new Detector({ formats: ['code_128'] })
      } catch {
        fail(CAMERA_ERRORS.decoder)
        return
      }

      const video = videoRef.current
      if (!video) {
        fail(CAMERA_ERRORS.start)
        return
      }

      try {
        video.srcObject = stream
        await video.play()
        if (!isCurrent()) {
          releaseMedia()
          return
        }
        setStarting(false)
        scheduleDetection()
      } catch (playError) {
        fail(cameraStartError(playError))
      }
    }

    void start()
    return () => {
      cancelled = true
      finished = true
      generationRef.current += 1
      releaseMedia()
    }
  }, [])

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
  const inputRevisionRef = useRef(0)
  const submittingRef = useRef(false)
  const focusTimerRef = useRef<number | null>(null)
  const submitUnlockTimerRef = useRef<number | null>(null)

  const submit = useCallback(
    (code: string) => {
      const trimmed = code.trim()
      if (!trimmed || disabled || submittingRef.current) return false

      submittingRef.current = true
      inputRevisionRef.current += 1
      if (debounceRef.current !== null) {
        window.clearTimeout(debounceRef.current)
        debounceRef.current = null
      }
      try {
        onScan(trimmed)
        setValue('')
        firstKeyTimeRef.current = 0
        if (focusTimerRef.current !== null) window.clearTimeout(focusTimerRef.current)
        focusTimerRef.current = window.setTimeout(() => inputRef.current?.focus(), 0)
        return true
      } finally {
        if (submitUnlockTimerRef.current !== null) {
          window.clearTimeout(submitUnlockTimerRef.current)
        }
        submitUnlockTimerRef.current = window.setTimeout(() => {
          submittingRef.current = false
          submitUnlockTimerRef.current = null
        }, 0)
      }
    },
    [disabled, onScan]
  )

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    return () => {
      if (debounceRef.current !== null) window.clearTimeout(debounceRef.current)
      if (focusTimerRef.current !== null) window.clearTimeout(focusTimerRef.current)
      if (submitUnlockTimerRef.current !== null) {
        window.clearTimeout(submitUnlockTimerRef.current)
      }
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
              const revision = ++inputRevisionRef.current
              if (!firstKeyTimeRef.current || now - firstKeyTimeRef.current > 400) {
                firstKeyTimeRef.current = now
              }
              setValue(next)
              if (debounceRef.current !== null) window.clearTimeout(debounceRef.current)
              if (!AUTO_SUBMIT_TOKEN.test(next)) {
                debounceRef.current = null
                return
              }
              debounceRef.current = window.setTimeout(() => {
                debounceRef.current = null
                if (revision !== inputRevisionRef.current) return
                const elapsed = Date.now() - firstKeyTimeRef.current
                if (elapsed < 350) submit(next)
              }, 120)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                if (debounceRef.current !== null) {
                  window.clearTimeout(debounceRef.current)
                  debounceRef.current = null
                }
                submit(e.currentTarget.value)
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
