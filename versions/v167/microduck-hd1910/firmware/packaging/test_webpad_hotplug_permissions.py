"""Exercise the shipped unit's socket policy with the real hotplug/cache bridge."""
import configparser
import errno
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

import webpad


class HotplugPermissions(unittest.TestCase):
    def test_shipped_unit_allows_input_events_to_invalidate_the_device_cache(self):
        # A fake monitor missed the regression: the shipped AF_UNIX-only unit
        # silently disabled InputMonitor and forced a device scan every 20 ms.
        unit = configparser.ConfigParser(interpolation=None)
        unit.read(Path(__file__).with_name('microduck-webpad.service'))
        allowed = set(unit['Service']['RestrictAddressFamilies'].split())
        receiver, sender = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)

        class UeventSocket:
            def bind(self, address):
                if address != (0, 1):
                    raise AssertionError(address)

            def setblocking(self, value):
                receiver.setblocking(value)

            def recv(self, size):
                return receiver.recv(size)

            def close(self):
                receiver.close()

        def restricted_socket(family, kind, protocol=0):
            if socket.AddressFamily(family).name not in allowed:
                raise OSError(errno.EAFNOSUPPORT, 'blocked by shipped unit')
            self.assertEqual((family, kind, protocol),
                             (socket.AF_NETLINK, socket.SOCK_DGRAM, 15))
            return UeventSocket()

        now, physical, scans, pads = [0.0], [], [], []

        class Pad:
            closed = False

            def send(self, *_):
                pass

            def close(self):
                self.closed = True

        def make_pad():
            pad = Pad()
            pads.append(pad)
            return pad

        try:
            with patch.object(webpad.socket, 'socket', side_effect=restricted_socket):
                monitor = webpad.InputMonitor()
            self.assertIsNotNone(monitor.socket, 'the shipped unit must permit AF_NETLINK')
            cache = webpad.DeviceCache(
                scanner=lambda: scans.append(1) or list(physical),
                monitor=monitor, clock=lambda: now[0])
            bridge = webpad.Bridge(make_pad, cache, clock=lambda: now[0],
                                   settings_loader=lambda: {})
            frame = {'action': 'state', 'owner': 'browser-test', 'frame': {'buttons': ['a']}}
            bridge.handle(frame)
            for _ in range(100):
                bridge.poll()
                bridge.status()
            self.assertEqual(len(scans), 1)

            # Unrelated uevents do not defeat caching; input events take effect
            # before the one-second fallback scan and revoke the virtual owner.
            now[0] = 0.1
            sender.send(b'SUBSYSTEM=power_supply\0')
            bridge.poll()
            self.assertEqual(len(scans), 1)
            physical.append({'name': 'Xbox'})
            sender.send(b'ACTION=add\0SUBSYSTEM=input\0')
            bridge.poll()
            self.assertEqual(len(scans), 2)
            self.assertTrue(pads[0].closed)
            self.assertIsNone(bridge.owner)
            self.assertTrue(bridge.status()['real_connected'])

            physical.clear()
            sender.send(b'ACTION=remove\0SUBSYSTEM=input\0')
            bridge.poll()
            self.assertFalse(bridge.status()['real_connected'])
            self.assertEqual(len(pads), 1)
            bridge.handle(frame)
            self.assertEqual(len(pads), 2)
            self.assertEqual(bridge.owner, 'browser-test')

            # A missed event still heals via the existing periodic rescan.
            physical.append({'name': 'Xbox'})
            now[0] = 1.11
            bridge.poll()
            self.assertTrue(pads[1].closed)
            self.assertTrue(bridge.status()['real_connected'])
        finally:
            receiver.close()
            sender.close()


if __name__ == '__main__':
    unittest.main()
