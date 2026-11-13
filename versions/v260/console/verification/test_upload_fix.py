"""Actual receiver, output backpressure, and handoff boundaries; no robot required."""
import io
import secrets
import shlex
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from service_control import ControlError, ServiceController, ServiceTransport
from staging_upload import StagingUpload
from telemetry import Store
from test_install_log157 import Channel


class UploadFailures(unittest.TestCase):
    def transfer(self, prefix='', progress=None, timeout=120):
        with tempfile.TemporaryDirectory(prefix='microduck-upgrade-', dir='/tmp') as temp:
            # The production receiver deliberately accepts a fixed internal path shape.
            path=Path('/tmp/microduck-upgrade-'+secrets.token_hex(6))
            path.mkdir()
            data=b'firmware'*131072
            def spawn(command, **options):
                args=shlex.split(command[-1]);args[2]=prefix+args[2]
                return subprocess.Popen(args, **options)
            try:
                with patch('staging_upload.ssh_command',return_value=['ssh','duck']), patch('staging_upload.ssh_process_options',return_value={}), patch('staging_upload.spawn_process',side_effect=spawn), patch('staging_upload.UPLOAD_TIMEOUT',timeout):
                    result=StagingUpload('duck').upload(str(path/'package.tar.gz'),io.BytesIO(data),len(data),progress,False)
                self.assertEqual((path/'package.tar.gz').read_bytes(),data)
                return result
            finally:
                (path/'package.tar.gz').unlink(missing_ok=True);path.rmdir()

    def test_large_stderr_cannot_block_input(self):
        self.transfer("import sys;sys.stderr.buffer.write(b'x'*262144);sys.stderr.flush();",timeout=3)

    def test_broken_pipe_keeps_receiver_error(self):
        with self.assertRaisesRegex(RuntimeError,'receiver disk full'):
            self.transfer("import sys;sys.stderr.write('receiver disk full\\n');sys.exit(7);",timeout=3)

    def test_timeout_is_explicit_and_bounded(self):
        start=time.monotonic()
        with self.assertRaisesRegex(TimeoutError,'中控已结束本次上传'):
            self.transfer('import time;time.sleep(10);',timeout=.2)
        self.assertLess(time.monotonic()-start,3)

    def test_display_exception_does_not_abort_transfer(self):
        self.transfer(progress=Mock(side_effect=RuntimeError('display failed')))


class HandoffBoundary(unittest.TestCase):
    def test_transport_does_not_handoff_until_upload_and_extract_succeed(self):
        for fail in ('','upload','tar'):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as temp:
                archive=Path(temp)/'package.tar.gz';archive.write_bytes(b'firmware')
                channel=Channel(fail=fail)
                transport=ServiceTransport('radxa@duck','/run/robotd.sock');transport.channel=channel
                handoff=Mock()
                def upload(*args,**kwargs):
                    handoff.assert_not_called()
                    if fail=='upload':raise RuntimeError('upload failed')
                def before_install():
                    self.assertTrue(any('tar' in args for args in channel.calls))
                    self.assertFalse(any('upgrade' in args for args in channel.calls))
                    handoff()
                with patch('service_control.bundle_info',return_value={}), patch.object(StagingUpload,'upload',upload):
                    if fail:
                        with self.assertRaises(ControlError):transport.upgrade(archive=archive,before_install=before_install)
                        handoff.assert_not_called()
                    else:
                        transport.upgrade(archive=archive,before_install=before_install)
                        handoff.assert_called_once()

    def test_upload_failure_leaves_existing_data_connection_open(self):
        store=Store('service');peer=Mock();store.install_handoff.attach(peer)
        def fail(*args,**kwargs):
            self.assertFalse(store.install_handoff.paused)
            self.assertFalse(store.robotd_restarting.is_set())
            raise ControlError('upload failed',503)
        service=ServiceController(store,transport=Mock(upgrade=fail),warm=False)
        job={'action':'upgrade-service','status':'running'}
        service._execute({'action':'upgrade-service','firmware':'bundled'},job,0)
        self.assertEqual(job['status'],'error')
        self.assertFalse(store.install_handoff.paused)
        peer.close.assert_not_called()


if __name__=='__main__':unittest.main()
