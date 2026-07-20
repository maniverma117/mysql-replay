import importlib
import time
import unittest
from queue import Queue
from unittest.mock import patch

import worker as worker_module

import config


class SmokeTests(unittest.TestCase):
    def test_state_module_and_app_import(self):
        state_module = importlib.import_module('state')
        self.assertTrue(hasattr(state_module, 'state'))

        try:
            app_module = importlib.import_module('app')
            self.assertTrue(hasattr(app_module, 'app'))
        except ModuleNotFoundError as exc:
            self.skipTest(f"Flask not installed: {exc}")

        payload = state_module.state.health()
        self.assertIn('status', payload)

        stats_payload = state_module.state.stats()
        self.assertIn('queries_executed', stats_payload)

    def test_fetcher_requests_loki_with_time_window(self):
        fetcher_module = importlib.import_module('fetcher')
        fetcher = fetcher_module.Fetcher(Queue(), state_module := importlib.import_module('state').state)

        class DummyResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"data": {"result": []}}

        with patch('fetcher.requests.get', return_value=DummyResponse()) as mocked_get:
            fetcher._fetch_logs()

        params = mocked_get.call_args.kwargs['params']
        self.assertEqual(params['query'], config.LOKI_QUERY)
        self.assertIn('start', params)
        self.assertIn('end', params)
        self.assertGreater(int(params['end']), int(params['start']))

    def test_worker_connect_returns_false_when_mysql_settings_missing(self):
        worker = worker_module.ReplayWorker(1, Queue())
        with patch.object(worker_module.config, 'MYSQL_HOST', ''), \
             patch.object(worker_module.config, 'MYSQL_DATABASE', ''), \
             patch.object(worker_module.config, 'MYSQL_USER', ''), \
             patch.object(worker_module.config, 'MYSQL_PASSWORD', ''):
            self.assertFalse(worker.connect())

    def test_worker_skips_obviously_incomplete_sql(self):
        worker = worker_module.ReplayWorker(1, Queue())
        worker.connection = object()
        worker.cursor = type('Cursor', (), {'execute': lambda self, sql: (_ for _ in ()).throw(AssertionError("should not execute"))})()

        self.assertIsNone(worker.execute("SELECT * FROM users WHERE"))

    def test_worker_handles_sql_error_without_crashing_thread(self):
        worker = worker_module.ReplayWorker(1, Queue())
        worker.connection = object()
        worker.cursor = type('Cursor', (), {'execute': lambda self, sql: (_ for _ in ()).throw(worker_module.mysql_connector.Error("boom"))})()
        with patch.object(worker.state, 'worker_busy'), patch.object(worker.state, 'worker_idle'), patch.object(worker.state, 'execution_failed'), patch.object(worker.state, 'update_queue'), patch.object(worker.state, 'execution_success'):
            worker.run()

    def test_worker_sets_session_max_execution_time_on_connect(self):
        worker = worker_module.ReplayWorker(1, Queue())
        dummy_cursor = type('Cursor', (), {
            'execute': lambda self, query: None,
        })()
        connected = type('Connected', (), {
            'cursor': lambda self: dummy_cursor,
            'close': lambda self: None,
        })()

        dummy_mysql = type('DummyMysql', (), {
            'connect': lambda *args, **kwargs: connected,
        })

        with patch.object(worker_module.config, 'MYSQL_QUERY_MAX_SECONDS', 60), \
             patch.object(worker_module.config, 'MYSQL_HOST', '127.0.0.1'), \
             patch.object(worker_module.config, 'MYSQL_DATABASE', 'test'), \
             patch.object(worker_module.config, 'MYSQL_USER', 'user'), \
             patch.object(worker_module.config, 'MYSQL_PASSWORD', 'pass'), \
             patch.object(worker_module, 'mysql_connector', dummy_mysql):
            self.assertTrue(worker.connect())


if __name__ == '__main__':
    unittest.main()
