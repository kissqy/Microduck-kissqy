"""Actual input streams stay independent of finite audio work; nothing is replayed."""
import json,socket,socketserver,threading,time,unittest
from io import BytesIO
from unittest.mock import patch
from controls import Controller,Transport,ControlError
import controls

class Store:
 def snapshot(self):return {'service_compatible':True,'bus':{'mode':'motion','phase':'control'}}
class Server(socketserver.ThreadingTCPServer):
 allow_reuse_address=True
 daemon_threads=True

class LatencyTests(unittest.TestCase):
 def test_connect_status_and_close_never_activate_an_input_socket(self):
  tr=Transport()
  with patch.object(controls,'open_remote_socket',side_effect=AssertionError('display activated webpad')):
   for _ in range(20):
    self.assertTrue(tr.call({'action':'connect'})['available'])
    self.assertTrue(tr.call({'action':'webpad_status'})['accepted'])
   tr.call({'action':'webpad_close','owner':'unused-page'})
   tr.reconnect_after_service();tr.close()
  self.assertIsNone(tr.peer)

 def test_slow_volume_does_not_block_input_or_snapshot_and_reuses_one_stream(self):
  commands=[];connections=[];audio_started=threading.Event();audio_release=threading.Event();errors=[]
  class Handler(socketserver.StreamRequestHandler):
   def handle(self):
    connections.append(1)
    for line in self.rfile:
     row=json.loads(line);commands.append(row)
     self.wfile.write((json.dumps({'accepted':True,'available':True,'owner':row['owner'],'frame':row.get('frame')})+'\n').encode())
  class Maintenance:
   def _manage(self,args,privileged):
    self.args,self.privileged=args,privileged;audio_started.set();audio_release.wait(3)
    return {'accepted':True,'audio':{'volume':72},'volume':72}
  server=Server(('127.0.0.1',0),Handler);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
  tr=Transport();maintenance=Maintenance();tr.attach_service_transport(maintenance);c=Controller(Store(),transport=tr)
  def volume():
   try:c.handle({'action':'set_volume','seq':1,'client':'latency-test','volume':72})
   except Exception as exc:errors.append(exc)
  try:
   with patch.object(controls,'open_remote_socket',side_effect=lambda *_a,**_kw:socket.create_connection(server.server_address)):
    slow=threading.Thread(target=volume);slow.start();self.assertTrue(audio_started.wait(1))
    at=time.monotonic();c.status();self.assertLess(time.monotonic()-at,.05)
    at=time.monotonic();frames=[]
    for seq,frame in [(3,{'buttons':['start']}),(4,{'buttons':[]}),(5,{'axes':{'rt':1}}),(6,{'axes':{'rt':0}})]:
     frames.append(c.handle({'action':'webpad_state','seq':seq,'client':'latency-test','frame':frame})['frame'])
    self.assertLess(time.monotonic()-at,.4,'audio must not hold input queue')
    self.assertEqual(connections,[1]);self.assertTrue(slow.is_alive())
    self.assertEqual(frames,[{'buttons':['start']},{'buttons':[]},{'axes':{'rt':1}},{'axes':{'rt':0}}])
    self.assertTrue(all(row['action']=='state' for row in commands));self.assertFalse(maintenance.privileged)
    self.assertEqual(maintenance.args[-2:],['set-volume','72'])
  finally:
   audio_release.set();slow.join(3);tr.close();server.shutdown();server.server_close();worker.join(2)
  self.assertEqual(errors,[])

 def test_live_pad_preferences_do_not_gate_web_input(self):
  class LiveStore(Store):
   def snapshot(self):return {**super().snapshot(),'service_control':{'busy':True,'job':{'action':'set-pad-settings'}}}
  class Fake:
   connected=True;audio_status={}
   def call(self,c):return {'accepted':True}
  self.assertTrue(Controller(LiveStore(),transport=Fake()).handle({'action':'webpad_state','client':'latency-test','seq':1,'frame':{'axes':{'lx':.4}}})['accepted'])

 def test_failed_input_is_not_replayed_and_next_fresh_gesture_opens_a_new_stream(self):
  devices=[]
  class Peer:
   def __init__(self):self.sent=[];self.closed=False;devices.append(self)
   def settimeout(self,_):pass
   def makefile(self,_):return BytesIO(b'' if len(devices)==1 else b'{"accepted":true,"owner":"test-page"}\n')
   def sendall(self,data):self.sent.append(json.loads(data))
   def close(self):self.closed=True
  tr=Transport()
  try:
   with patch.object(controls,'open_remote_socket',side_effect=lambda *_a,**_kw:Peer()):
    with self.assertRaisesRegex(ControlError,'本次输入未重发'):tr.call({'action':'webpad_state','owner':'test-page','frame':{'buttons':['start']}})
    self.assertEqual(len(devices),1)
    self.assertTrue(tr.call({'action':'webpad_state','owner':'test-page','frame':{'buttons':['y']}})['accepted'])
   self.assertEqual([r['frame']['buttons'] for d in devices for r in d.sent],[['start'],['y']]);self.assertTrue(devices[0].closed)
  finally:tr.close()

 def test_delayed_close_for_old_browser_does_not_drop_current_owner(self):
  class Peer:
   closed=False
   def settimeout(self,_):pass
   def makefile(self,_):return BytesIO(b'{"accepted":true,"owner":"new-page"}\n')
   def sendall(self,data):self.sent=json.loads(data)
   def close(self):self.closed=True
  peer=Peer();tr=Transport();tr.peer=peer;tr.reader=peer.makefile('rb')
  try:
   with patch.object(controls.select,'select',return_value=([],[],[])):
    tr.call({'action':'webpad_close','owner':'old-page'})
   self.assertIs(tr.peer,peer);self.assertFalse(peer.closed)
  finally:tr.close()

 def test_slow_initial_socket_open_keeps_ready_channel_for_next_fresh_gesture(self):
  class Peer:
   closed=False
   def __init__(self):self.sent=[]
   def settimeout(self,_):pass
   def makefile(self,_):return BytesIO(b'{"accepted":true,"owner":"test-page"}\n')
   def sendall(self,data):self.sent.append(json.loads(data))
   def close(self):self.closed=True
  peer=Peer();tr=Transport();opens=[]
  def open_slow(*_a,**_kw):
   opens.append(1);time.sleep(.42);return peer
  try:
   with patch.object(controls,'open_remote_socket',side_effect=open_slow),patch.object(controls.select,'select',return_value=([],[],[])):
    with self.assertRaisesRegex(ControlError,'输入已过期'):tr.call({'action':'webpad_state','owner':'test-page','frame':{'buttons':['start']}})
    self.assertEqual(peer.sent,[]);self.assertIs(tr.peer,peer);self.assertFalse(peer.closed)
    # UI cleanup for an unsent frame must not destroy the completed handshake.
    tr.call({'action':'webpad_close','owner':'test-page'})
    self.assertFalse(peer.closed);self.assertEqual(peer.sent,[])
    result=tr.call({'action':'webpad_state','owner':'test-page','frame':{'buttons':['y']}})
    self.assertTrue(result['accepted']);self.assertEqual(opens,[1])
    self.assertEqual([row['frame']['buttons'] for row in peer.sent],[['y']])
  finally:tr.close()

 def test_eof_replacement_opens_while_old_forward_reference_is_still_held(self):
  class Peer:
   closed=False
   def settimeout(self,_):pass
   def makefile(self,_):return BytesIO(b'{"accepted":true,"owner":"test-page"}\n')
   def sendall(self,data):self.sent=json.loads(data)
   def close(self):self.closed=True
  old,new=Peer(),Peer();tr=Transport();tr.peer=old;tr.reader=old.makefile('rb')
  def replace(*_a,**_kw):
   self.assertFalse(old.closed,'release after opening to reuse SSH authentication')
   return new
  try:
   with patch.object(controls,'open_remote_socket',side_effect=replace),patch.object(controls.select,'select',return_value=([old],[],[])):
    self.assertTrue(tr.call({'action':'webpad_state','owner':'test-page','frame':{'buttons':['start']}})['accepted'])
   self.assertTrue(old.closed);self.assertIs(tr.peer,new)
  finally:tr.close()

 def test_close_on_eof_only_retires_stream_and_never_activates_another_worker(self):
  class Peer:
   closed=False
   def close(self):self.closed=True
  peer=Peer();tr=Transport();tr.peer=peer;tr.reader=BytesIO()
  with patch.object(controls,'open_remote_socket',side_effect=AssertionError('close reactivated webpad')),patch.object(controls.select,'select',return_value=([peer],[],[])):
   self.assertTrue(tr.call({'action':'webpad_close','owner':'test-page'})['accepted'])
  self.assertTrue(peer.closed);self.assertIsNone(tr.peer)

if __name__=='__main__':unittest.main()
