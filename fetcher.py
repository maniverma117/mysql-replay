"""
Fetcher for replaying Loki log entries into a work queue.
"""

import re
import time
from datetime import datetime, timedelta
from typing import Optional

import requests
from requests.exceptions import RequestException

import config
from logger import logger
from state import state


class Fetcher:

    def __init__(self, sql_queue, state_manager):
        self.sql_queue = sql_queue
        self.state = state_manager
        self.last_error: Optional[str] = None

    def _fetch_logs(self):
        headers = {"Accept": "application/json"}
        end = datetime.utcnow()
        start = end - timedelta(hours=config.LOKI_LOOKBACK_HOURS)
        base_params = {
            "limit": config.LOKI_LIMIT,
            "start": str(int(start.timestamp() * 1_000_000_000)),
            "end": str(int(end.timestamp() * 1_000_000_000)),
        }

        query_candidates = []
        if config.LOKI_QUERY:
            query_candidates.append(config.LOKI_QUERY)
        else:
            query_candidates.append('{job=~".+"}')

        last_error = None
        for query in query_candidates:
            params = {"query": query, **base_params}
            for attempt in range(1, config.LOKI_RETRY_COUNT + 1):
                try:
                    response = requests.get(
                        config.LOKI_URL + "/loki/api/v1/query_range",
                        params=params,
                        headers=headers,
                        timeout=config.LOKI_REQUEST_TIMEOUT,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    return payload.get("data", {}).get("result", [])
                except RequestException as exc:
                    last_error = exc
                    logger.warning(
                        "Loki query failed (attempt %d/%d) for %s: %s",
                        attempt,
                        config.LOKI_RETRY_COUNT,
                        query,
                        exc,
                    )
                    if attempt < config.LOKI_RETRY_COUNT:
                        time.sleep(config.LOKI_RETRY_DELAY)

        raise last_error or RuntimeError("Unable to fetch logs from Loki")

    def _extract_sql(self, entry) -> Optional[str]:
        values = entry.get("values", [])
        if not values:
            return None

        raw_text = values[-1][1] if values else ""
        if not raw_text:
            return None

        candidate = raw_text.strip()
        match = re.search(r"(?is)\b(select)\b.+", candidate)
        if not match:
            return None

        sql = match.group(0).strip()
        sql = sql.rstrip(" ;")
        return sql if sql else None

    def run(self):
        while True:
            try:
                start = datetime.utcnow()
                results = self._fetch_logs()
                count = 0
                for entry in results:
                    sql = self._extract_sql(entry)
                    if sql:
                        self.sql_queue.put((datetime.utcnow(), sql))
                        count += 1
                end = datetime.utcnow()
                self.state.fetch_started(start, end)
                self.state.add_fetched(count)
                self.state.update_queue(self.sql_queue.qsize())
                self.last_error = None
                time.sleep(config.POLL_INTERVAL)
            except Exception as exc:
                self.last_error = str(exc)
                logger.exception("Fetcher failed: %s", exc)
                time.sleep(10)
