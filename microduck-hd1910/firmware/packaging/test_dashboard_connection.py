"""Connection switches all existing transports; no startup probe or robot action."""
import json, os, subprocess, sys, tempfile, threading, time, unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'console'))
from connection import Connection
from controls import Controller, ControlError
from service_control import ServiceController
from telemetry import Store
from ssh_connect import ssh_command, ssh_process_options, login_password


class DashboardConnectionTests(unittest.TestCase):
    def setUp(self):
        self.store = Store('service')
        self.controls = Controller(self.store)
        self.service = ServiceController(self.store, controls=self.controls, warm=False)
        self.config = {'camera_host': 'original', 'ssh_target': None}
        self.calls = []
        def collector(target, config, emit, stop, log, paused):
            self.calls.append((target, emit, stop))
            emit({'channel': 'system', 'data': {'hostname': target}})
            stop.wait(5)
        self.connection = Connection(self.store, self.config, self.controls, self.service, collector, {})
        self.saved = patch('connection.save_target'); self.saved.start()
    def tearDown(self):
        self.connection.close(); self.controls.close(); self.service.close(); self.saved.stop()
    def test_startup_waits_for_page_connect_without_launching_process_or_collector(self):
        self.assertEqual(self.calls, [])
        self.assertTrue(self.store.connection_paused.is_set())
        self.assertIsNone(self.service.transport.channel.proc)
        self.assertFalse(self.connection.status()['active'])
    def test_address_password_and_camera_switch_together_without_action(self):
        self.connection.handle({'action': 'connect', 'target': '192.168.6.150', 'password': 'first 密码'})
        first = self.calls[-1]
        self.assertEqual(self.controls.transport.target, 'radxa@192.168.6.150')
        self.assertEqual(self.service.transport.target, self.controls.transport.target)
        self.assertEqual(self.config['camera_host'], '192.168.6.150')
        self.assertIs(self.service.transport.credential, __import__('ssh_connect')._credentials[self.controls.transport.target])
        options = ssh_process_options(self.controls.transport.target)
        self.assertEqual(options['env']['MICRODUCK_SSH_PASSWORD'], 'first 密码')
        self.assertNotIn('first 密码', ' '.join(ssh_command(self.controls.transport.target)))
        self.connection.handle({'action': 'connect', 'target': 'other@192.168.6.151', 'password': 'second'})
        self.assertTrue(first[2].is_set())
        first[1]({'channel': 'system', 'data': {'hostname': 'stale'}})
        self.assertNotEqual(self.store.data.get('system', {}).get('hostname'), 'stale')
        self.assertEqual(self.service.transport.target, 'other@192.168.6.151')
        self.assertIsNone(self.controls.transport.peer)
        self.assertIsNone(self.controls.transport.reader)
        self.assertIsNone(self.service.transport.channel.proc)
    def test_blank_password_reuses_shared_credential_and_forget_clears_both_uses(self):
        target = 'reuse@192.168.6.151'
        self.connection.handle({'action': 'connect', 'target': target, 'password': 'saved'})
        self.connection.handle({'action': 'connect', 'target': target, 'password': ''})
        self.assertEqual(login_password(target), 'saved')
        self.service.transport.forget_sudo_password()
        self.assertIsNone(login_password(target))
        self.assertNotIn('MICRODUCK_SSH_PASSWORD', ssh_process_options(target)['env'])
    def test_disconnect_stops_collection_and_pauses_transports_without_home_or_relax(self):
        self.connection.handle({'action': 'connect', 'target': '192.168.6.151'})
        worker = self.calls[-1]
        result = self.connection.handle({'action': 'disconnect'})
        self.assertFalse(result['active']); self.assertTrue(worker[2].is_set())
        self.assertTrue(self.controls.transport.suspended)
        self.assertIsNone(self.service.job)
    def test_invalid_input_does_not_disconnect_current_target(self):
        self.connection.handle({'action': 'connect', 'target': '192.168.6.151'})
        with self.assertRaises(ControlError): self.connection.handle({'action': 'connect', 'target': ';invalid'})
        self.assertTrue(self.connection.status()['active'])

if __name__ == '__main__': unittest.main()
