"""Use real local TCP and the production HTTP upgrade/dispatcher, without motors."""
import base64
from http.server import ThreadingHTTPServer
import io
import json
import socket
import struct
import threading
import time
import unittest
from urllib.request import Request, urlopen

from console import handler_for
from controls import Controller
from control_socket import read_frame, ProtocolError


def masked(payload, opcode=1, fin=True):
    payload = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    mask = b'1234'
    n = len(payload)
    head = bytes(((128 if fin else 0) | opcode, 128 | n)) if n < 126 else bytes(((128 if fin else 0) | opcode, 254)) + struct.pack('!H', n)
    return head + mask + bytes(v ^ mask[i % 4] for i, v in enumerate(payload))


class Store:
    def snapshot(self):
        return {'service_compatible': True, 'bus': {'mode': 'motion', 'phase': 'control', 'homed': False}}


class Transport:
    connected = True
    audio_status = {}
    log = None
    def __init__(self):self.calls=[];self.released=threading.Event()
    def call(self, command):
        self.calls.append(command)
        if command['action']=='webpad_close':self.released.set()
        return {'accepted':True,'available':True,'real_connected':False}


class SocketTests(unittest.TestCase):
    def setUp(self):
        self.transport=Transport();self.controller=Controller(Store(),transport=self.transport)
        self.slow=threading.Event()
        class Management:
            def connection(inner):self.slow.set();time.sleep(.5);return {'management_revision':'R17'}
        self.config={'bind':'127.0.0.1','service_enabled':True,'control_token':'socket-test'}
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(Store(),self.config,self.controller,Management()))
        self.server.daemon_threads=True
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.host='127.0.0.1:'+str(self.server.server_port)
        self.peers=[]
    def tearDown(self):
        for peer in self.peers:peer.close()
        self.server.shutdown();self.server.server_close();self.thread.join()
    def connect(self, token='socket-test',origin=None):
        peer=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=2);self.peers.append(peer)
        reader=peer.makefile('rb')
        peer.sendall(('GET /api/control/socket HTTP/1.1\r\nHost: '+self.host+'\r\nOrigin: '+(origin or 'http://'+self.host)+'\r\nUpgrade: websocket\r\nConnection: keep-alive,Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: '+base64.b64encode(b'0123456789abcdef').decode()+'\r\nSec-WebSocket-Protocol: r17-control, r17-auth.'+token+'\r\n\r\n').encode())
        status=reader.readline();headers={}
        while True:
            line=reader.readline()
            if line==b'\r\n':break
            key,value=line.decode().split(':',1);headers[key.lower()]=value.strip()
        return peer,reader,status,headers
    @staticmethod
    def receive(reader):
        a,b=reader.read(2);size=b&127
        if size==126:size=struct.unpack('!H',reader.read(2))[0]
        return a&15,reader.read(size)
    def test_single_socket_orders_press_release_and_revokes_on_disconnect(self):
        peer,reader,status,headers=self.connect()
        self.assertIn(b'101',status);self.assertEqual(headers['sec-websocket-protocol'],'r17-control')
        for i,buttons in enumerate((['start'],[],['y']),1):
            peer.sendall(masked({'id':i,'payload':{'action':'webpad_state','client':'socket-page','seq':i,'frame':{'buttons':buttons}}}))
            opcode,payload=self.receive(reader);self.assertEqual(opcode,1)
            answer=json.loads(payload);self.assertEqual(answer['id'],i);self.assertTrue(answer['result']['accepted'])
        self.assertEqual([r['frame']['buttons'] for r in self.transport.calls],[['start'],[],['y']])
        # No fabricated Select release; cleanup goes through an owner-scoped close.
        peer.shutdown(socket.SHUT_RDWR);reader.close();peer.close()
        self.assertTrue(self.transport.released.wait(1));self.assertEqual(self.transport.calls[-1],{'action':'webpad_close','owner':'socket-page'})
        self.assertFalse(self.controller.sequences)
    def test_slow_http_management_does_not_queue_websocket_input(self):
        peer,reader,_,_=self.connect()
        errors=[]
        def maintenance():
            try:
                req=Request('http://'+self.host+'/api/service/connection',data=b'{}',headers={'Content-Type':'application/json','Origin':'http://'+self.host,'X-Control-Token':'socket-test'})
                with urlopen(req,timeout=2) as reply:reply.read()
            except Exception as exc:errors.append(exc)
        worker=threading.Thread(target=maintenance);worker.start();self.assertTrue(self.slow.wait(1))
        started=time.monotonic()
        peer.sendall(masked({'id':1,'payload':{'action':'webpad_state','client':'socket-page','seq':1,'frame':{'axes':{'lx':.5}}}}))
        self.assertTrue(json.loads(self.receive(reader)[1])['result']['accepted'])
        self.assertLess(time.monotonic()-started,.2,'input waited behind a 500 ms management HTTP request')
        peer.shutdown(socket.SHUT_RDWR);reader.close();worker.join();self.assertEqual(errors,[])
    def test_wrong_credentials_and_foreign_origin_never_dispatch(self):
        for token,origin in [('wrong',None),('socket-test','http://foreign.invalid')]:
            peer,reader,status,_=self.connect(token,origin);self.assertIn(b'403',status);reader.close();peer.close()
        self.assertFalse(self.transport.calls)
    def test_unmasked_and_oversized_frames_rejected_before_json_dispatch(self):
        for data in [b'\x81\x02{}',b'\x81\xfe'+struct.pack('!H',4097)]:
            with self.assertRaises(ProtocolError):read_frame(io.BytesIO(data))


if __name__=='__main__':unittest.main()
