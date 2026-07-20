"""
Shared application state for the MySQL Buffer Pool Warmer.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from threading import Lock
from typing import Deque, Dict, Optional


class StateManager:

    def __init__(self):
        self.lock = Lock()
        self.started = datetime.utcnow()

        self.fetch_cycles = 0
        self.queries_fetched = 0
        self.last_fetch_start = None
        self.last_fetch_end = None

        self.queries_executed = 0
        self.queries_failed = 0
        self.last_success = None
        self.last_failure = None

        self.queue_size = 0
        self.max_queue_size = 0

        self.total_execution_time = 0.0
        self.max_execution_time = 0.0
        self.avg_execution_time = 0.0

        self.worker_states: Dict[int, Dict[str, Optional[str]]] = {}
        self.logs: Deque[Dict[str, object]] = deque(maxlen=200)

    def _record_log(self, level: str, message: str, **context) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            **context,
        }
        with self.lock:
            self.logs.append(entry)

    def fetch_started(self, start: datetime, end: datetime) -> None:
        with self.lock:
            self.fetch_cycles += 1
            self.last_fetch_start = start.isoformat()
            self.last_fetch_end = end.isoformat()
        self._record_log("INFO", "Fetcher cycle started", started=start.isoformat(), ended=end.isoformat())

    def add_fetched(self, count: int) -> None:
        with self.lock:
            self.queries_fetched += count
        self._record_log("INFO", "Fetched queries", count=count)

    def update_queue(self, size: int) -> None:
        with self.lock:
            self.queue_size = size
            if size > self.max_queue_size:
                self.max_queue_size = size

    def worker_busy(self, worker_id: int, sql: str) -> None:
        with self.lock:
            self.worker_states[worker_id] = {
                "status": "busy",
                "started": datetime.utcnow().isoformat(),
                "query": sql[:200],
            }
        self._record_log("INFO", f"Worker {worker_id} busy", worker_id=worker_id)

    def worker_idle(self, worker_id: int) -> None:
        with self.lock:
            self.worker_states[worker_id] = {
                "status": "idle",
                "started": None,
                "query": None,
            }
        self._record_log("INFO", f"Worker {worker_id} idle", worker_id=worker_id)

    def execution_success(self, elapsed: float) -> None:
        with self.lock:
            self.queries_executed += 1
            self.last_success = datetime.utcnow().isoformat()
            self.total_execution_time += elapsed
            if elapsed > self.max_execution_time:
                self.max_execution_time = elapsed
            if self.queries_executed > 0:
                self.avg_execution_time = self.total_execution_time / self.queries_executed

    def execution_failed(self) -> None:
        with self.lock:
            self.queries_failed += 1
            self.last_failure = datetime.utcnow().isoformat()

    def health(self) -> Dict[str, object]:
        with self.lock:
            return {
                "status": "ok",
                "service": "mysql-bufferpool-warmer",
                "started": self.started.isoformat(),
                "uptime_seconds": int((datetime.utcnow() - self.started).total_seconds()),
            }

    def stats(self) -> Dict[str, object]:
        with self.lock:
            return {
                "started": self.started.isoformat(),
                "fetch_cycles": self.fetch_cycles,
                "queries_fetched": self.queries_fetched,
                "queries_executed": self.queries_executed,
                "queries_failed": self.queries_failed,
                "queue_size": self.queue_size,
                "max_queue_size": self.max_queue_size,
                "last_fetch_start": self.last_fetch_start,
                "last_fetch_end": self.last_fetch_end,
                "last_success": self.last_success,
                "last_failure": self.last_failure,
                "avg_execution_time": round(self.avg_execution_time, 3),
                "max_execution_time": round(self.max_execution_time, 3),
                "workers": self.worker_states,
            }

    def workers(self) -> Dict[str, object]:
        with self.lock:
            serializable_workers = {}
            for worker_id, worker_state in self.worker_states.items():
                if isinstance(worker_state, dict):
                    serializable_workers[str(worker_id)] = {
                        key: (value if value is None or isinstance(value, (str, int, float, bool)) else str(value))
                        for key, value in worker_state.items()
                    }
                else:
                    serializable_workers[str(worker_id)] = worker_state
            return {"workers": serializable_workers}

    def queue(self) -> Dict[str, object]:
        with self.lock:
            return {"queue_size": self.queue_size, "max_queue_size": self.max_queue_size}

    def logs(self) -> Dict[str, object]:
        with self.lock:
            return {"logs": list(self.logs)}


state = StateManager()
