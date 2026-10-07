"""Exercise the production selector worker with a real inherited-style listener."""
import configparser
import json
import os
from pathlib import Path
import socket
import threading
import time
import unittest
from unittest.mock import patch

import webpad


class ActivationTests(unittest.TestCase):
    def test_systemd_fd_is_used_without_rebinding_or_unlinking_listener(self):
        marker=object()
        with patch.dict(os.environ,{'LISTEN_PID':str(os.getpid()),'LISTEN_FDS':'1'}),patch.object(webpad.socket,'socket',return_value=marker) as create:
            self.assertEqual(webpad.activated_listener(),(marker,True))
            create.assert_called_once_with(fileno=3)
            self.assertNotIn('LISTEN_PID',os.environ)
            self.assertNotIn('LISTEN_FDS',os.environ)

    def test_shipped_socket_keeps_existing_robot_group_access_and_no_worker_boot_enable(self):
        socket_unit=configparser.ConfigParser(interpolation=None);socket_unit.read(Path(__file__).with_name('microduck-webpad.socket'))
        service=configparser.ConfigParser(interpolation=None);service.read(Path(__file__).with_name('microduck-webpad.service'))
        self.assertEqual(socket_unit['Socket']['SocketGroup'],'robot')
        self.assertEqual(socket_unit['Socket']['SocketMode'],'0660')
        self.assertEqual(socket_unit['Socket']['ListenStream'],str(webpad.SOCKET))
        self.assertEqual(service['Service']['Sockets'],'microduck-webpad.socket')
        self.assertNotIn('Install',service)
        self.assertNotIn('RuntimeDirectory',service['Service'],'systemd listener owns its path across idle exits')

    def test_worker_releases_on_disconnect_exits_idle_and_can_be_activated_again(self):
        pads=[];errors=[]
        class Tap:
            name=webpad.NAME
            generation=0
        class Pad:
            def __init__(self):self.frames=[];self.closed=False;pads.append(self)
            def send(self,axes,buttons):self.frames.append((axes,buttons))
            def close(self):self.closed=True
        class Monitor:
            socket=None
            def changed(self):return False
            def close(self):pass
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(8)
        def run():
            try:webpad.serve()
            except BaseException as exc:errors.append(exc)
        def start_worker():
            worker=threading.Thread(target=run,daemon=True);worker.start();return worker
        try:
            # The original systemd-held listener survives the worker's duplicate
            # closing. TCP substitutes only for this executor's restricted AF_UNIX.
            with patch.object(webpad,'activated_listener',side_effect=lambda:(listener.dup(),True)),patch.object(webpad,'PadTap',Tap),patch.object(webpad,'Xbox',Pad),patch.object(webpad,'InputMonitor',Monitor),patch.object(webpad,'DeviceCache',return_value=lambda:[]),patch.object(webpad,'SettingsCache',return_value=lambda:{}),patch.object(webpad,'IDLE_EXIT',.15):
                for buttons in (['lb'],['start'],['y']):
                    worker=start_worker()
                    with socket.create_connection(listener.getsockname(),timeout=1) as peer:
                        peer.settimeout(1)
                        with peer.makefile('rb') as reader:
                            peer.sendall((json.dumps({'action':'state','owner':'test-page','frame':{'buttons':buttons}})+'\n').encode())
                            self.assertTrue(json.loads(reader.readline())['accepted'])
                            self.assertEqual(pads[-1].frames,[],'an input acknowledgement must not bypass padd attachment')
                            Tap.generation+=1
                            limit=time.monotonic()+.4
                            while not pads[-1].frames and time.monotonic()<limit:time.sleep(.005)
                            self.assertEqual(pads[-1].frames[0][1],set(buttons),'first edge waits for padd attach then reaches original mapping')
                            peer.sendall(b'{"action":"close","owner":"old-page"}\n')
                            self.assertEqual(json.loads(reader.readline())['owner'],'test-page','old owner close must keep current connection ownership')
                    limit=time.monotonic()+.15
                    while not pads[-1].closed and time.monotonic()<limit:time.sleep(.005)
                    self.assertTrue(pads[-1].closed,'EOF releases owner before 600 ms lease deadline')
                    worker.join(1);self.assertFalse(worker.is_alive(),'no polling worker remains after idle')
                self.assertEqual(len(pads),3,'next activation does not reuse or replay old input')
        finally:listener.close()
        self.assertEqual(errors,[])

    def test_idle_status_client_cannot_keep_the_worker_running(self):
        class Tap:pass
        class Monitor:
            socket=None
            def changed(self):return False
            def close(self):pass
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(8);errors=[]
        def run():
            try:webpad.serve()
            except BaseException as exc:errors.append(exc)
        try:
            with patch.object(webpad,'activated_listener',side_effect=lambda:(listener.dup(),True)),patch.object(webpad,'PadTap',Tap),patch.object(webpad,'InputMonitor',Monitor),patch.object(webpad,'DeviceCache',return_value=lambda:[]),patch.object(webpad,'SettingsCache',return_value=lambda:{}),patch.object(webpad,'IDLE_EXIT',.12),patch.object(webpad,'Xbox',side_effect=AssertionError('status created Xbox')):
                worker=threading.Thread(target=run,daemon=True);worker.start()
                with socket.create_connection(listener.getsockname(),timeout=1) as peer,peer.makefile('rb') as reader:
                    peer.settimeout(1);peer.sendall(b'{"action":"status"}\n')
                    self.assertTrue(json.loads(reader.readline())['accepted'])
                    worker.join(.5);self.assertFalse(worker.is_alive())
                    self.assertEqual(reader.readline(),b'')
        finally:listener.close()
        self.assertEqual(errors,[])


if __name__=='__main__':unittest.main()
