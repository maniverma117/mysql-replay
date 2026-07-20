"""
worker.py

Replay SELECT statements from the queue to the new Read Replica.
"""

import re
import time

try:
    import mysql.connector as mysql_connector
except ModuleNotFoundError:  # pragma: no cover - exercised when dependency is absent
    mysql_connector = None
else:
    mysql_connector = mysql_connector

import config

from logger import logger
from state import state


class ReplayWorker:

    def __init__(self, worker_id, sql_queue, state_manager=None):
        self.worker_id = worker_id
        self.sql_queue = sql_queue
        self.state = state_manager or state
        self.connection = None
        self.cursor = None

    def connect(self):
        while True:
            try:
                if mysql_connector is None:
                    raise RuntimeError("mysql-connector-python is not installed")
                if not config.MYSQL_HOST or not config.MYSQL_DATABASE or not config.MYSQL_USER or not config.MYSQL_PASSWORD:
                    raise RuntimeError("MYSQL_HOST, MYSQL_DATABASE, MYSQL_USER, and MYSQL_PASSWORD must be configured")

                logger.info("Worker-%s connecting to MySQL...", self.worker_id)
                self.connection = mysql_connector.connect(
                    host=config.MYSQL_HOST,
                    port=config.MYSQL_PORT,
                    user=config.MYSQL_USER,
                    password=config.MYSQL_PASSWORD,
                    database=config.MYSQL_DATABASE,
                    connection_timeout=config.MYSQL_CONNECT_TIMEOUT,
                    read_timeout=config.MYSQL_READ_TIMEOUT,
                    write_timeout=config.MYSQL_WRITE_TIMEOUT,
                    consume_results=True,
                )
                self.cursor = self.connection.cursor()

                if config.MYSQL_QUERY_MAX_SECONDS > 0:
                    try:
                        self.cursor.execute(
                            f"SET SESSION MAX_EXECUTION_TIME = {config.MYSQL_QUERY_MAX_SECONDS * 1000}"
                        )
                    except Exception as exc:
                        logger.warning(
                            "Worker-%s unable to set session query timeout: %s",
                            self.worker_id,
                            exc,
                        )

                logger.info("Worker-%s connected.", self.worker_id)
                return True
            except RuntimeError as exc:
                logger.error("Worker-%s configuration error: %s", self.worker_id, exc)
                return False
            except Exception:
                logger.exception("Worker-%s unable to connect. Retrying in 5 seconds...", self.worker_id)
                time.sleep(5)

    def reconnect(self):
        try:
            if self.cursor:
                self.cursor.close()
        except Exception:
            pass

        try:
            if self.connection:
                self.connection.close()
        except Exception:
            pass

        self.connection = None
        self.cursor = None
        self.connect()

    def _ensure_connected(self):
        if self.connection is not None and self.cursor is not None:
            return True
        return self.connect()

    def _is_query_timeout_error(self, exc):
        if not isinstance(exc, Exception):
            return False
        text = str(exc).lower()
        return (
            "query execution was interrupted" in text or
            "max_execution_time" in text or
            "timed out" in text or
            "timed out" in text
        )

    def _is_probably_invalid_sql(self, sql):
        if not isinstance(sql, str):
            return True
        stripped = sql.strip()
        if not stripped:
            return True
        if re.search(r"\b(select|show|describe|explain)\b", stripped, re.IGNORECASE) and re.search(r"\b(from|where|join|group by|order by|limit)\b", stripped, re.IGNORECASE) is None:
            return True
        if re.search(r"\b(from|where|join|group by|order by|limit)\b", stripped, re.IGNORECASE) and stripped.endswith(("WHERE", "FROM", "JOIN", "ON", "LEFT", "RIGHT", "INNER", "OUTER", "GROUP", "ORDER", "LIMIT")):
            return True
        if stripped.endswith(("AND", "OR", "AS", "ON", "WHERE")):
            return True
        if stripped.count("(") != stripped.count(")"):
            return True
        return False

    def execute(self, sql):
        if self._is_probably_invalid_sql(sql):
            logger.warning("[Worker-%s] Skipping malformed SQL: %s", self.worker_id, sql)
            return None

        if self.connection is None or self.cursor is None:
            raise RuntimeError("MySQL connection is not available")

        start = time.time()
        self.cursor.execute(sql)
        try:
            self.cursor.fetchall()
        except mysql_connector.Error:
            raise
        except Exception as exc:
            logger.warning("[Worker-%s] Fetch error after execute: %s", self.worker_id, exc)
            raise
        elapsed = time.time() - start
        return elapsed

    def run(self):
        if not self.connect():
            return
        logger.info("Worker-%s started", self.worker_id)

        while True:
            try:
                if not self._ensure_connected():
                    return

                timestamp, sql = self.sql_queue.get()
                self.state.worker_busy(self.worker_id, sql)

                try:
                    elapsed = self.execute(sql)
                    if elapsed is None:
                        self.state.execution_failed()
                        logger.info("[Worker-%s] SKIPPED malformed SQL | Queue=%d", self.worker_id, self.sql_queue.qsize())
                    else:
                        self.state.execution_success(elapsed)
                        logger.info("[Worker-%s] SUCCESS %.3fs | Queue=%d", self.worker_id, elapsed, self.sql_queue.qsize())
                except mysql_connector.Error as exc:
                    error_text = str(exc)
                    if self._is_query_timeout_error(exc):
                        self.state.execution_failed()
                        logger.warning(
                            "[Worker-%s] Query exceeded max execution time: %s (%s)",
                            self.worker_id,
                            sql,
                            exc,
                        )
                        self.connection = None
                        self.cursor = None
                    elif isinstance(exc, mysql_connector.ProgrammingError) and "Unknown column" in error_text:
                        self.state.execution_failed()
                        logger.warning("[Worker-%s] Unsupported schema query: %s (%s)", self.worker_id, sql, exc)
                    else:
                        logger.warning("[Worker-%s] MySQL error for SQL: %s (%s)", self.worker_id, sql, exc)
                        self.reconnect()
                        try:
                            elapsed = self.execute(sql)
                            if elapsed is None:
                                self.state.execution_failed()
                                logger.info("[Worker-%s] SKIPPED malformed SQL after reconnect | Queue=%d", self.worker_id, self.sql_queue.qsize())
                            else:
                                self.state.execution_success(elapsed)
                                logger.info("[Worker-%s] SUCCESS AFTER RECONNECT %.3fs", self.worker_id, elapsed)
                        except Exception as retry_exc:
                            self.state.execution_failed()
                            logger.warning("[Worker-%s] FAILED AFTER RECONNECT for SQL: %s (%s)", self.worker_id, sql, retry_exc)
                except Exception as exc:
                    self.state.execution_failed()
                    logger.warning("[Worker-%s] Query Failed for SQL: %s (%s)", self.worker_id, sql, exc)
                finally:
                    self.state.worker_idle(self.worker_id)
                    self.state.update_queue(self.sql_queue.qsize())
                    self.sql_queue.task_done()
            except Exception as exc:
                logger.exception("[Worker-%s] Unexpected worker error, reconnecting and continuing: %s", self.worker_id, exc)
                self.connection = None
                self.cursor = None
                time.sleep(1)
                continue

                