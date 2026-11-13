"""Automatic query outcomes stay readable without changing returned data."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from controls import Transport
from service_control import ControlError, ServiceController, ServiceTransport
from system_log import SystemLog
from telemetry import Store


class Channel:
    def __init__(self, payload, stderr='', returncode=0):
        self.payload, self.stderr, self.returncode = payload, stderr, returncode
        self.calls = []
    def request(self, request, timeout, **kwargs):
        self.calls.append(request)
        assert not request.get('progress'), 'automatic query must not stream raw data'
        return {'returncode': self.returncode, 'stdout': json.dumps(self.payload), 'stderr': self.stderr}


class InlineThread:
    def __init__(self, target, **kwargs): self.target = target
    def start(self): self.target()


class QueryLogTests(unittest.TestCase):
    def test_model_query_returns_identical_catalogue_with_one_summary(self):
        data = {'models': [{'id': 'a', 'sha256': '0'*64, 'name': 'walk'}],
                'slots': [{'slot': 'walk', 'model': {'id': 'a'}}, {'slot': 'kick_left', 'label': '左踢', 'model': None}]}
        with tempfile.TemporaryDirectory() as directory:
            log = SystemLog(directory)
            try:
                transport = ServiceTransport('', '/unused', log)
                channel = transport.channel = Channel(data)
                store = Store('service'); store.system_log = log
                store.snapshot = lambda: {'bus': {'build': '1fa8438-feetech-ft6-control.36'}}
                service = ServiceController(store, transport=transport, warm=False)
                self.assertEqual(service.models(), data)
                self.assertEqual(len(channel.calls), 1)
                log.flush(); text = log.path.read_text()
                self.assertIn('成功 · 已读取 1 个模型配置：walk；未配置：左踢', text)
                self.assertNotIn('"models"', text); self.assertNotIn('0'*64, text)
                self.assertEqual([e['source'] for e in log.tail()['entries']], ['模型配置'])
            finally: log.close()

    def test_query_failure_keeps_complete_stderr_and_does_not_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            log = SystemLog(directory)
            try:
                transport = ServiceTransport('', '/unused', log)
                transport.channel = Channel({}, 'FIRST-FAILURE\n' + 'x'*6000 + '\nLAST-FAILURE', 1)
                with self.assertRaises(ControlError): transport.manage('models', privileged=False, record_output=False)
                log.flush(); text = log.path.read_text()
                self.assertIn('FIRST-FAILURE', text); self.assertIn('LAST-FAILURE', text)
                self.assertEqual(len(transport.channel.calls), 1)
            finally: log.close()

    def test_model_query_json_error_keeps_the_helper_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            log = SystemLog(directory)
            try:
                transport = ServiceTransport('', '/unused', log)
                transport.channel = Channel({'error': 'model manifest missing'})
                store = Store('service'); store.system_log = log
                store.snapshot = lambda: {'bus': {'build': '1fa8438-feetech-ft6-control.36'}}
                service = ServiceController(store, transport=transport, warm=False)
                with self.assertRaisesRegex(ControlError, 'model manifest missing'): service.models()
                log.flush(); self.assertIn('失败 · model manifest missing', log.path.read_text())
            finally: log.close()

    def test_invalid_query_json_keeps_original_output(self):
        class Invalid(Channel):
            def request(self, *args, **kwargs):
                return {'returncode': 0, 'stdout': 'broken-query-json', 'stderr': 'original diagnostic'}
        with tempfile.TemporaryDirectory() as directory:
            log = SystemLog(directory)
            try:
                transport = ServiceTransport('', '/unused', log); transport.channel = Invalid(None)
                with self.assertRaisesRegex(ControlError, 'JSON'): transport.manage('models', privileged=False, record_output=False)
                log.flush(); self.assertIn('broken-query-json', log.path.read_text()); self.assertIn('original diagnostic', log.path.read_text())
            finally: log.close()

    def test_volume_load_once_returns_same_value_without_mixer_dump(self):
        with tempfile.TemporaryDirectory() as directory:
            log = SystemLog(directory)
            try:
                service = ServiceTransport('', '/unused', log)
                service.channel = Channel({'accepted': True, 'audio': {'volume': 5, 'initializing': False}},
                                          '音量命令: amixer\n音量回读: 退出码 0\nnumid=26\n: values=75,75\n')
                controls = Transport(system_log=log); controls.service_transport = service
                with patch('controls.threading.Thread', InlineThread):
                    controls._load_audio_once(); controls._load_audio_once()
                self.assertEqual(len(service.channel.calls), 1); self.assertEqual(controls.audio_status['volume'], 5)
                log.flush(); text = log.path.read_text()
                self.assertIn('系统音量] 读取成功 · 5%', text)
                self.assertNotIn('amixer', text); self.assertNotIn('numid', text)
            finally: log.close()

    def test_failed_initial_volume_is_reported_without_success_or_input_action(self):
        with tempfile.TemporaryDirectory() as directory:
            log = SystemLog(directory)
            try:
                service = ServiceTransport('', '/unused', log)
                service.channel = Channel({'accepted': True, 'audio': {'volume': None, 'message': '音量未确认：声卡不可用'}})
                controls = Transport(system_log=log); controls.service_transport = service
                with patch('controls.threading.Thread', InlineThread): controls._load_audio_once()
                self.assertIsNone(controls.input_channel); self.assertNotIn('volume', controls.audio_status)
                log.flush(); text = log.path.read_text()
                self.assertIn('读取失败', text); self.assertIn('声卡不可用', text); self.assertNotIn('读取成功', text)
            finally: log.close()


if __name__ == '__main__': unittest.main()
