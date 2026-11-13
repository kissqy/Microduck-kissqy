import importlib.util
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

PC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PC / 'verification/v230'))
from test_support import FW
sys.path.insert(0, str(FW / 'system-repair'))
from microduck_wifi_r7 import WifiStartup
from microduck_wifi_events import NetworkEvents


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path, loader=SourceFileLoader(name, str(path)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixtures = load(PC / 'verification/v230/test_wifi_r7.py', 'v231_network_fixture')
dispatcher = load(FW / 'system-repair/90-microduck-hotspot', 'v231_dispatcher_fixture')


class FakeEvents:
    def __init__(self, callbacks=()):
        self.callbacks = list(callbacks)
        self.waits = []
        self.clears = 0
        self.wakes = 0
    def clear(self): self.clears += 1
    def wake(self): self.wakes += 1
    def wait(self, timeout=None):
        self.waits.append(timeout)
        if not self.callbacks:
            raise AssertionError('unexpected wait without an event or recovery action')
        self.callbacks.pop(0)()
        return True


class EventWifiTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.profile = self.root / 'Microduck-Setup.nmconnection'
        self.clock = fixtures.Clock()
        self.network = fixtures.Network(self.clock, self.profile)
        self.env = {'time': self.clock, 'run': self.network.run, 'INTERFACE': 'auto',
                    'AP_NAME': 'Microduck-kissqy', 'SETUP_IP': '10.42.0.1',
                    'disable_captive_dns': Mock()}
        self.startup = WifiStartup(self.env, self.profile)
        self.env['show_hotspot_with_captive'] = self.startup.activate_hotspot

    def test_connected_idle_waits_for_event_without_periodic_queries(self):
        self.network.mode = 'home'
        stopped = [False]
        def no_notifications_for_an_hour():
            self.clock.now += 3600
            stopped[0] = True
        events = FakeEvents([no_notifications_for_an_hour])
        self.assertTrue(self.startup.monitor_home_wifi(events, lambda: stopped[0]))
        state_queries = [args for args, _ in self.network.calls if 'GENERAL.STATE,GENERAL.CONNECTION,IP4.ADDRESS' in args]
        self.assertEqual(len(state_queries), 1)
        self.assertEqual(events.waits, [None])
        self.assertEqual(self.network.ap_ups(), [])

    def test_disconnect_notification_starts_hotspot_and_preserves_profile(self):
        fixtures.profile(self.profile, 'keep-owner-password')
        original = self.profile.read_bytes()
        self.network.mode = 'home'
        stopped = [False]
        events = FakeEvents([lambda: setattr(self.network, 'mode', 'none')])
        def serve(**kwargs): stopped[0] = True
        self.startup.run_forever(serve, events, lambda: stopped[0])
        self.assertEqual(self.network.mode, 'ap')
        self.assertEqual(len(self.network.ap_ups()), 1)
        self.assertEqual(self.profile.read_bytes(), original)
        self.assertEqual(events.waits, [None])

    def test_new_card_without_saved_network_starts_hotspot(self):
        stopped = [False]
        self.startup.run_forever(lambda **_: stopped.__setitem__(0, True), FakeEvents(), lambda: stopped[0])
        self.assertEqual(self.network.mode, 'ap')

    def test_stale_notification_reads_live_state_and_keeps_working_wifi(self):
        self.network.mode = 'home'
        stopped = [False]
        events = FakeEvents([lambda: None, lambda: stopped.__setitem__(0, True)])
        self.startup.run_forever(Mock(), events, lambda: stopped[0])
        self.assertEqual(self.network.ap_ups(), [])
        self.assertEqual(events.waits, [None, None])

    def test_ip_loss_notification_is_offline_even_if_nm_state_is_connected(self):
        self.network.mode = 'home'
        events = FakeEvents([lambda: setattr(self.network, 'no_ip', True)])
        self.assertFalse(self.startup.monitor_home_wifi(events, lambda: False))
        self.assertEqual(events.waits, [None])

    def test_query_error_retries_without_taking_over_a_working_connection(self):
        self.network.mode = 'home'
        original = self.network.run
        failed = [False]
        def run(*args, **kwargs):
            if not failed[0]:
                failed[0] = True
                raise OSError('temporary local NM failure')
            return original(*args, **kwargs)
        self.env['run'] = run
        stopped = [False]
        events = FakeEvents([lambda: None, lambda: stopped.__setitem__(0, True)])
        self.startup.monitor_home_wifi(events, lambda: stopped[0])
        self.assertEqual(self.network.ap_ups(), [])
        self.assertEqual(events.waits, [30, None])

    def test_dispatcher_and_receiver_use_real_datagrams_with_socketpair_transport(self):
        # This executor permits socketpair but blocks pathname socket creation.
        # Keep the real byte transport and receiver thread; replace only bind
        # and destination routing. Board pathname binding remains a field test.
        path = self.root / 'events.sock'
        receiver, sender = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.addCleanup(receiver.close)
        self.addCleanup(sender.close)
        class Receiver:
            def bind(self, name): Path(name).touch()
            def recv(self, length): return receiver.recv(length)
            def close(self): receiver.close()
        class Sender:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def settimeout(self, timeout): sender.settimeout(timeout)
            def sendto(self, raw, name):
                if name != str(path): raise AssertionError('wrong event destination')
                return sender.send(raw)
        with patch.object(socket, 'socket', side_effect=[Receiver(), Sender(), Sender(), Sender(), Sender()]):
            with NetworkEvents(lambda: 'wlan0', path) as events:
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                dispatcher.notify('wlan0', 'down', str(path))
                self.assertTrue(events.wait(1))
                events.clear()
                dispatcher.notify('eth0', 'down', str(path))
                self.assertFalse(events.wait(.05))
                dispatcher.notify('wlan0', 'dhcp4-change', str(path))
                self.assertTrue(events.wait(1))
        self.assertFalse(path.exists())
        self.assertFalse(events.worker.is_alive())

    def test_failed_activation_backs_off_even_when_it_generates_down_events(self):
        stopped = [False]
        events = FakeEvents()
        def failed():
            events.wake()
            raise RuntimeError('activation failed')
        self.env['show_hotspot_with_captive'] = failed
        original = self.clock.sleep
        def sleep(seconds):
            original(seconds)
            if seconds == 30: stopped[0] = True
        self.clock.sleep = sleep
        self.startup.run_forever(Mock(), events, lambda: stopped[0])
        self.assertGreaterEqual(self.clock.now, 30)
        self.assertEqual(events.waits, [])

    def test_notification_during_query_is_not_lost(self):
        self.network.mode = 'home'
        stopped = [False]
        class PendingEvents:
            pending = False
            def clear(self): self.pending = False
            def wake(self): self.pending = True
            def wait(self, timeout=None):
                self.assert_pending()
                stopped[0] = True
            def assert_pending(self):
                if not self.pending: raise AssertionError('notification lost')
        events = PendingEvents()
        original = self.network.run
        def run(*args, **kwargs):
            result = original(*args, **kwargs)
            events.wake()
            return result
        self.env['run'] = run
        self.assertTrue(self.startup.monitor_home_wifi(events, lambda: stopped[0]))


def portal_scope():
    raw = (FW / 'system-repair/microduck-public-image.sh').read_text()
    source = raw.split('#__PORTAL_BEGIN__\n', 1)[1].split('#__PORTAL_END__', 1)[0]
    env = {'__name__': 'v231_portal_fixture'}
    exec(compile(source, 'v231-portal', 'exec'), env)
    return env


class PortalEventsTests(unittest.TestCase):
    def test_old_staging_marker_does_not_disable_recovery(self):
        env = portal_scope()
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / 'skip-until-sealed'
            marker.touch()
            env['STAGING_PATH'] = marker
            env['_wifi_startup_r7'].run_forever = Mock()
            context = Mock()
            context.__enter__ = Mock(return_value=FakeEvents())
            context.__exit__ = Mock(return_value=False)
            with patch('microduck_wifi_events.NetworkEvents', return_value=context), \
                 patch.object(sys, 'argv', ['portal', '--serve', 'auto']):
                env['main']()
            env['_wifi_startup_r7'].run_forever.assert_called_once()

    def test_provisioning_notifies_after_success_and_failure(self):
        for failed in (False, True):
            with self.subTest(failed=failed), tempfile.TemporaryDirectory() as folder:
                env = portal_scope()
                env['NETWORK_EVENTS'] = Mock()
                env['PROVISIONED_PATH'] = Path(folder) / 'provisioned'
                env['WIFI_PATH'] = Path(folder) / 'home.nmconnection'
                env['time'] = fixtures.Clock()
                def run(*args, **kwargs):
                    return SimpleNamespace(returncode=1 if failed and args[0] == 'chpasswd' else 0, stdout='', stderr='')
                env['run'] = run
                env['secure_profile'] = Mock(return_value=fixtures.HOME_UUID)
                env['home_ready'] = lambda: True
                env['show_hotspot'] = Mock()
                env['INTERFACE'] = 'wlan0'
                env['STATE']['busy'] = True
                server = Mock()
                env['provision']('fixture', 'fixture-password', 'fixture-system-password', server)
                self.assertFalse(env['STATE']['busy'])
                self.assertEqual(env['STATE']['success'], not failed)
                env['NETWORK_EVENTS'].wake.assert_called_once()

    def test_portal_waits_for_events_and_does_not_interrupt_provisioning(self):
        env = portal_scope()
        workers = []
        servers = []
        class Thread:
            def __init__(self, **kwargs): self.alive = False; workers.append(self)
            def start(self): self.alive = True
            def is_alive(self): return self.alive
            def join(self, **kwargs): pass
        class Server:
            def __init__(self, address, handler):
                servers.append(self)
                if len(servers) == 1: env['STATE']['busy'] = True
                self.closed = False
            def serve_forever(self, **kwargs): pass
            def shutdown(self):
                for worker in workers: worker.alive = False
            def server_close(self): self.closed = True
        env['threading'] = SimpleNamespace(Thread=Thread)
        env['ThreadingHTTPServer'] = Server
        env['disable_captive_dns'] = Mock()
        def query():
            if not env.get('query_raced'):
                env['query_raced'] = True
                env['STATE']['busy'] = True
                return 'offline'
            return 'wifi'
        env['_wifi_startup_r7'].link_kind = Mock(side_effect=query)
        events = FakeEvents([lambda: env['STATE'].update(busy=False),
                             lambda: env['STATE'].update(busy=False)])
        env['serve_setup_portal'](events=events)
        self.assertEqual(events.waits, [None, None])
        self.assertEqual(env['_wifi_startup_r7'].link_kind.call_count, 2)
        self.assertTrue(all(server.closed for server in servers))

    def test_installer_installs_executable_dispatcher(self):
        module = load(FW / 'system-repair/install-system-repair.py', 'v231_install_fixture')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            module.apply(root, live=False)
            hook = root / module.DISPATCHER
            self.assertEqual(hook.stat().st_mode & 0o777, 0o755)
            self.assertEqual(hook.read_bytes(), (FW / 'system-repair/90-microduck-hotspot').read_bytes())
            self.assertTrue((root / module.EVENT_MODULE).is_file())


if __name__ == '__main__': unittest.main()
