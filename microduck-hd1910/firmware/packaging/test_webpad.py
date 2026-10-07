"""Input arbitration and hotplug acknowledgement; no robot/serial dependencies."""
import math,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import webpad
from controls import Controller,ControlError

class Device:
 def __init__(self):self.frames=[];self.closed=False
 def send(self,*frame):self.frames.append(frame)
 def close(self):self.closed=True
class InputTests(unittest.TestCase):
 def setUp(self):
  self.now=0;self.real=[];self.devices=[];self.ready=True
  def create():d=Device();self.devices.append(d);return d
  self.bridge=webpad.Bridge(create,lambda:self.real,lambda:self.now,lambda _:self.ready)
 def state(self,owner='test-page',buttons=[]):return self.bridge.handle({'action':'state','owner':owner,'frame':{'buttons':buttons}})
 def test_physical_takeover_destroys_virtual_device_and_requires_new_browser_input(self):
  self.state(buttons=['select']);d=self.devices[0];self.real=[{'name':'GameSir Xbox','event':'event1'}];self.bridge.poll()
  self.assertTrue(d.closed);self.assertIsNone(self.bridge.pad);self.assertFalse(self.state()['accepted'])
  self.real=[];self.bridge.poll();self.assertIsNone(self.bridge.pad)
  self.assertTrue(self.state()['accepted']);self.assertEqual(len(self.devices),2)
 def test_lease_expiry_and_close_never_fabricate_select_release(self):
  self.state(buttons=['select']);d=self.devices[0];self.now=.601;self.bridge.poll()
  self.assertTrue(d.closed);self.assertEqual(len(d.frames),1);self.assertIn('select',d.frames[0][1])
  self.state();self.bridge.handle({'action':'close','owner':'other-page'});self.assertIsNotNone(self.bridge.pad)
  self.bridge.handle({'action':'close','owner':'test-page'});self.assertIsNone(self.bridge.pad)
 def test_first_start_and_release_are_buffered_until_unmodified_padd_attaches(self):
  self.ready=False;self.state(buttons=['start']);self.state(buttons=[]);d=self.devices[0];self.assertEqual(d.frames,[])
  self.bridge.poll();self.assertEqual(d.frames,[]);self.ready=True;self.bridge.poll();self.bridge.poll()
  self.assertEqual([f[1] for f in d.frames],[{'start'},set()])
 def test_first_lb_and_release_wait_for_padd_without_sending_start(self):
  # LB can now be the first gesture from limp; hotplug must not lose its edge
  # or manufacture the HOME command that this recovery is meant to avoid.
  self.ready=False;self.state(buttons=['lb']);self.state(buttons=[]);d=self.devices[0]
  self.bridge.poll();self.assertEqual(d.frames,[])
  self.ready=True;self.bridge.poll();self.bridge.poll()
  self.assertEqual([f[1] for f in d.frames],[{'lb'},set()])
  self.assertTrue(all(not any(axes.values()) for axes,_ in d.frames))
  # Select keeps its original press/release path after the recovery request.
  self.state(buttons=['select']);self.state(buttons=[])
  self.assertEqual([f[1] for f in d.frames],[{'lb'},set(),{'select'},set()])
 def test_lb_waiting_for_attach_expires_without_later_replay(self):
  self.ready=False;self.state(buttons=['lb']);self.state(buttons=[]);d=self.devices[0]
  self.now=webpad.TIMEOUT+.001;self.ready=True;self.bridge.poll()
  self.assertTrue(d.closed);self.assertEqual(d.frames,[]);self.assertFalse(self.bridge.pending)
  self.bridge.poll();self.assertIsNone(self.bridge.pad)
  self.state(buttons=['lb'])
  self.assertEqual(len(self.devices),2)
  self.assertEqual([f[1] for f in self.devices[1].frames],[{'lb'}])
 def test_pending_lb_is_discarded_by_physical_takeover_or_owner_close(self):
  for cancellation in ('physical','close'):
   with self.subTest(cancellation=cancellation):
    self.setUp();self.ready=False;self.state(buttons=['lb']);self.state(buttons=[]);d=self.devices[0]
    if cancellation=='physical':
     self.real=[{'name':'GameSir Xbox','event':'event1'}];self.bridge.poll();self.real=[]
    else:self.bridge.handle({'action':'close','owner':'test-page'})
    self.ready=True;self.bridge.poll()
    self.assertTrue(d.closed);self.assertEqual(d.frames,[]);self.assertFalse(self.bridge.pending)
    self.assertIsNone(self.bridge.owner);self.assertIsNone(self.bridge.pad)
 def test_real_takeover_discards_first_start_waiting_for_attach(self):
  self.ready=False;self.state(buttons=['start']);d=self.devices[0];self.real=[{'name':'real'}];self.bridge.poll();self.ready=True;self.bridge.poll()
  self.assertTrue(d.closed);self.assertEqual(d.frames,[]);self.assertFalse(self.bridge.pending)
 def test_second_page_cannot_capture_an_existing_controller(self):
  self.state();self.assertFalse(self.state('other-page')['accepted']);self.assertEqual(self.bridge.owner,'test-page')
 def test_nonfinite_or_out_of_range_axes_rejected_before_device_creation(self):
  for axes in ({'lx':math.nan},{'ly':1.01},{'lt':-.1},{'dx':.5},{'lx':True},{'unknown':0}):
   with self.assertRaises(ValueError):self.bridge.handle({'action':'state','owner':'test-page','frame':{'axes':axes}})
  self.assertFalse(self.devices)
 def test_physical_detection_uses_capabilities_and_excludes_our_virtual_pad(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   for i,name in enumerate((webpad.NAME,'GameSir R7','keyboard')):
    node=root/f'event{i}'/'device';(node/'capabilities').mkdir(parents=True);(node/'name').write_text(name)
    keys=(1<<0x130) if i<2 else 1
    words=[]
    while keys:words.append(f'{keys&((1<<64)-1):x}');keys>>=64
    (node/'capabilities/key').write_text(' '.join(reversed(words)));(node/'capabilities/abs').write_text('3')
   self.assertEqual(webpad.real_gamepads(root),[{'name':'GameSir R7','event':'event1'}])
 def test_web_gate_allows_first_start_before_home_and_rejects_old_custom_motion(self):
  class Store:
   def snapshot(self):return {'service_compatible':True,'bus':{'mode':'motion','phase':'control','homed':False,'policy_enabled':False}}
  class Transport:
   connected=True;audio_status={}
   def call(self,c):return {'accepted':True,**c}
  c=Controller(Store(),transport=Transport());frame={'action':'webpad_state','client':'test-page','seq':1,'frame':{'buttons':['start']}}
  self.assertTrue(c.handle(frame)['accepted'])
  with self.assertRaises(ControlError):c.handle(frame)
  with self.assertRaises(ControlError):c.handle({'action':'move','client':'test-page','seq':2})
 def test_fallen_limp_lb_and_select_are_plain_controller_frames(self):
  class Store:
   def snapshot(self):return {'service_compatible':True,'bus':{'mode':'motion','phase':'control','homed':False,'policy_enabled':False,'fallen':True,'torque_enabled':False}}
  class Transport:
   connected=True;audio_status={}
   def __init__(self):self.calls=[]
   def call(self,c):self.calls.append(c);return {'accepted':True}
  transport=Transport();c=Controller(Store(),transport=transport)
  for seq,buttons in enumerate((['lb'],[],['select'],[]),1):
   self.assertTrue(c.handle({'action':'webpad_state','client':'test-page','seq':seq,'frame':{'buttons':buttons}})['accepted'])
  self.assertEqual(transport.calls,[{'action':'webpad_state','owner':'test-page','frame':{'buttons':buttons}} for buttons in (['lb'],[],['select'],[])])
if __name__=='__main__':unittest.main()
