
"""Offline tests of cron log parsing, without starting a Flask server."""
from datetime import datetime, timedelta, timezone
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

fake_flask = types.ModuleType('flask')

class FakeFlask:
    def __init__(self, _name):
        pass

    def route(self, *_args, **_kwargs):
        return lambda fn: fn

fake_flask.Flask = FakeFlask
fake_flask.jsonify = lambda data: data
fake_cors = types.ModuleType('flask_cors')
fake_cors.CORS = lambda _app: None

with tempfile.TemporaryDirectory() as tmp:
    LOG_PATH = Path(tmp) / 'cron.log'
    LOG_PATH.write_text('')
    with patch.dict(sys.modules, {'flask': fake_flask, 'flask_cors': fake_cors}):
        with patch.dict(os.environ, {'LOG_PATH': str(LOG_PATH)}):
            path = Path(__file__).resolve().parents[1] / 'cron-status' / 'app.py'
            spec = importlib.util.spec_from_file_location('cron_status_tested', path)
            status = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(status)

NOW = datetime(2026, 11, 19, 15, 0, tzinfo=timezone.utc)
GOOD = '2026-11-19 14:10:01,123 - cron - INFO - ## Cron scheduler started\n2026-11-19 14:10:02,123 - cron - INFO - Job completed: OpenMeteoInfluxCronjob, execution time: 12s\n'

class CronTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'cron.log'
        status.LOG_PATH = str(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def write_log(self, content, age_minutes=15):
        self.path.write_text(content)
        t = (NOW - timedelta(minutes=age_minutes)).timestamp()
        os.utime(self.path, (t, t))

    def test_missing_log_unknown(self):
        self.assertEqual(status.read_cronjob_status(NOW)['status'], 'unknown')

    def test_new_log_with_successful_job_green(self):
        self.write_log(GOOD)
        result = status.read_cronjob_status(NOW)
        self.assertEqual(result['status'], 'success')
        self.assertIsNotNone(result['last_activity_at'])

    def test_old_log_never_green(self):
        self.write_log(GOOD, age_minutes=200)
        self.assertEqual(status.read_cronjob_status(NOW)['status'], 'error')

    def test_log_failure_overrides_recent_completion(self):
        self.write_log(GOOD + '2026-11-19 - cron - ERROR - Job failed with error\n')
        self.assertEqual(status.read_cronjob_status(NOW)['status'], 'error')

    def test_no_start_or_completion_not_green(self):
        self.write_log('Random text without markers\n')
        self.assertEqual(status.read_cronjob_status(NOW)['status'], 'unknown')
        self.write_log('2026-11-19 - INFO - ## Cron scheduler started\n')
        self.assertEqual(status.read_cronjob_status(NOW)['status'], 'unknown')

if __name__ == '__main__':
    unittest.main()
