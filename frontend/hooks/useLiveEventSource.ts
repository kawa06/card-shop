'use client'

import { useEffect, useRef } from 'react'

type LiveEventHandler = (event: { type: string; stream_id: number; payload: Record<string, unknown>; ts: string }) => void

function parseSseChunk(buffer: string): { events: LiveEventHandler extends (e: infer E) => void ? E : never[]; rest: string } {
  const events: { type: string; stream_id: number; payload: Record<string, unknown>; ts: string }[] = []
  const parts = buffer.split('\n\n')
  const rest = parts.pop() ?? ''
  for (const part of parts) {
    const lines = part.split('\n')
    let dataLine = ''
    for (const line of lines) {
      if (line.startsWith('data:')) dataLine = line.slice(5).trim()
    }
    if (!dataLine || dataLine === '{}') continue
    try {
      events.push(JSON.parse(dataLine))
    } catch {
      // ignore malformed chunks
    }
  }
  return { events, rest }
}

export function useLiveEventSource(
  url: string | null,
  onEvent: LiveEventHandler,
  options?: { enabled?: boolean; getAuthHeaders?: () => Promise<Record<string, string>> },
) {
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent
  const enabled = options?.enabled !== false

  useEffect(() => {
    if (!url || !enabled) return
    let cancelled = false
    let retryMs = 1000
    let reader: ReadableStreamDefaultReader<Uint8Array> | null = null
    let abort: AbortController | null = null

    const connect = async () => {
      while (!cancelled) {
        abort = new AbortController()
        try {
          const headers = (await options?.getAuthHeaders?.()) ?? {}
          const res = await fetch(url, {
            headers: { Accept: 'text/event-stream', ...headers },
            credentials: 'include',
            signal: abort.signal,
            cache: 'no-store',
          })
          if (!res.ok || !res.body) throw new Error(`SSE ${res.status}`)
          reader = res.body.getReader()
          const decoder = new TextDecoder()
          let buffer = ''
          retryMs = 1000
          while (!cancelled) {
            const { done, value } = await reader.read()
            if (done) break
            buffer += decoder.decode(value, { stream: true })
            const parsed = parseSseChunk(buffer)
            buffer = parsed.rest
            for (const evt of parsed.events) onEventRef.current(evt)
          }
        } catch {
          if (cancelled) break
          await new Promise((r) => setTimeout(r, retryMs))
          retryMs = Math.min(retryMs * 2, 15000)
        } finally {
          try {
            await reader?.cancel()
          } catch {
            // ignore
          }
          reader = null
          abort = null
        }
      }
    }

    connect()
    return () => {
      cancelled = true
      abort?.abort()
      reader?.cancel().catch(() => undefined)
    }
  }, [url, enabled, options?.getAuthHeaders])
}
