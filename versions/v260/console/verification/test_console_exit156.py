"""Exit releases session files even if a connection teardown fails."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from system_log import SystemLog


class LogExitTests(unittest.TestCase):
    def test_close_drains_output_and_releases_the_file_and_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            log = SystemLog(directory)
            for index in range(100): log.add('session', f'line {index}')
            log.close()
            self.assertTrue(log.stream.closed)
            self.assertFalse(log.worker.is_alive())
            self.assertEqual(len(log.path.read_text().splitlines()), 100)
            log.close()
            log.add('late reader', 'must not reopen the session file')
            log.flush()
            log.path.unlink()
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_flush_failure_still_signals_waiter_and_releases_file(self):
        with tempfile.TemporaryDirectory() as directory:
            log = SystemLog(directory)
            stream = log.stream
            wrapped = Mock(wraps=stream)
            wrapped.flush.side_effect = OSError('injected flush failure')
            log.stream = wrapped
            log.flush()
            self.assertIn('injected flush failure', log.error)
            log.close()
            self.assertTrue(stream.closed)
            self.assertFalse(log.worker.is_alive())


class ConsoleExitTests(unittest.TestCase):
    def test_one_teardown_error_does_not_skip_other_owners_or_log(self):
        import console
        controls, service, connection, server, log = [Mock() for _ in range(5)]
        service.close.side_effect = RuntimeError('injected channel-close failure')
        server.serve_forever.side_effect = KeyboardInterrupt()
        with patch.object(console, 'Controller', return_value=controls), \
             patch('service_control.ServiceController', return_value=service), \
             patch('connection.Connection', return_value=connection), \
             patch.object(console, 'ThreadingHTTPServer', return_value=server), \
             patch('system_log.SystemLog', return_value=log), \
             patch.object(console, 'close_owned_processes') as retire, \
             contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()) as errors:
            console.main(['--dashboard', '--feetech'])
        for owner in (controls, service, connection, log): owner.close.assert_called_once()
        server.server_close.assert_called_once()
        retire.assert_called_once()
        self.assertIn('injected channel-close failure', errors.getvalue())


if __name__ == '__main__': unittest.main()
