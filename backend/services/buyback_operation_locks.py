"""In-process companion locks for SQLite/dev; database row locks remain authoritative."""

from __future__ import annotations

import threading
import weakref
from contextlib import contextmanager
from collections.abc import Iterator

_guard = threading.Lock()
_locks: weakref.WeakValueDictionary[int, threading.RLock] = (
    weakref.WeakValueDictionary()
)


@contextmanager
def request_operation_lock(request_id: int) -> Iterator[None]:
    with _guard:
        lock = _locks.get(request_id)
        if lock is None:
            lock = threading.RLock()
            _locks[request_id] = lock
    with lock:
        yield
