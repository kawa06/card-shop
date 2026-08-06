"""Write Phase 3-1 SSE files as UTF-8 (Windows-safe)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LIVE_EVENTS = '''"""In-process SSE hub for live streams (Phase 3-1 Milestone 3)."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from queue import Empty, Full, Queue
from typing import Any, AsyncIterator, Literal, Optional

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

Audience = Literal["public", "admin"]
MAX_CONNECTIONS_PER_STREAM = 300
MAX_GLOBAL_CONNECTIONS = 2000
HEARTBEAT_SECONDS = 20
QUEUE_MAXSIZE = 64


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"


@dataclass
class LiveEvent:
    type: str
    stream_id: int
    payload: dict[str, Any] = field(default_factory=dict)
    audience: Audience | Literal["both"] = "both"
    ts: str = field(default_factory=_utcnow_iso)

    def to_sse(self) -> str:
        body = {
            "type": self.type,
            "stream_id": self.stream_id,
            "payload": self.payload,
            "ts": self.ts,
        }
        return f"event: {self.type}\ndata: {json.dumps(body, ensure_ascii=False)}\n\n"


@dataclass
class _Subscriber:
    queue: Queue[str]
    audience: Audience


class LiveEventHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: dict[int, list[_Subscriber]] = {}
        self._global_count = 0

    @property
    def global_connections(self) -> int:
        with self._lock:
            return self._global_count

    def _register(self, stream_id: int, audience: Audience) -> _Subscriber:
        with self._lock:
            if self._global_count >= MAX_GLOBAL_CONNECTIONS:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Live event connection limit reached",
                )
            stream_list = self._subs.setdefault(stream_id, [])
            if len(stream_list) >= MAX_CONNECTIONS_PER_STREAM:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Stream event connection limit reached",
                )
            sub = _Subscriber(queue=Queue(maxsize=QUEUE_MAXSIZE), audience=audience)
            stream_list.append(sub)
            self._global_count += 1
            return sub

    def _unregister(self, stream_id: int, sub: _Subscriber) -> None:
        with self._lock:
            stream_list = self._subs.get(stream_id, [])
            if sub in stream_list:
                stream_list.remove(sub)
            if not stream_list and stream_id in self._subs:
                del self._subs[stream_id]
            self._global_count = max(0, self._global_count - 1)

    def publish(
        self,
        stream_id: int,
        event_type: str,
        payload: Optional[dict[str, Any]] = None,
        *,
        audience: Audience | Literal["both"] = "both",
    ) -> None:
        event = LiveEvent(type=event_type, stream_id=stream_id, payload=payload or {}, audience=audience)
        message = event.to_sse()
        with self._lock:
            targets = list(self._subs.get(stream_id, []))
        for sub in targets:
            if audience != "both" and sub.audience != audience:
                continue
            try:
                sub.queue.put_nowait(message)
            except Full:
                logger.warning("Dropping live SSE event for slow subscriber stream=%s", stream_id)

    async def stream(self, stream_id: int, audience: Audience) -> AsyncIterator[str]:
        sub = self._register(stream_id, audience)
        try:
            connected = json.dumps({"stream_id": stream_id, "audience": audience})
            yield f"event: connected\ndata: {connected}\n\n"
            while True:
                try:
                    message = await asyncio.to_thread(sub.queue.get, True, HEARTBEAT_SECONDS)
                    yield message
                except Empty:
                    yield ": heartbeat\n\n"
        finally:
            self._unregister(stream_id, sub)


live_event_hub = LiveEventHub()


def emit_live_event(
    stream_id: int,
    event_type: str,
    payload: Optional[dict[str, Any]] = None,
    *,
    audience: Audience | Literal["both"] = "both",
) -> None:
    live_event_hub.publish(stream_id, event_type, payload, audience=audience)
'''

HOOK = """'use client'

import { useEffect, useRef } from 'react'

type LiveEventHandler = (event: { type: string; stream_id: number; payload: Record<string, unknown>; ts: string }) => void

function parseSseChunk(buffer: string): { events: LiveEventHandler extends (e: infer E) => void ? E : never[]; rest: string } {
  const events: { type: string; stream_id: number; payload: Record<string, unknown>; ts: string }[] = []
  const parts = buffer.split('\\n\\n')
  const rest = parts.pop() ?? ''
  for (const part of parts) {
    const lines = part.split('\\n')
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
"""


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    print("wrote", path)


if __name__ == "__main__":
    write(ROOT / "backend/services/live_events.py", LIVE_EVENTS)
    write(ROOT / "frontend/hooks/useLiveEventSource.ts", HOOK)
