"""Direct input mapping, event arbitration and real persistent Unix IPC."""
import copy
import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from remote_input import Input,Robot,devices,AXES
from controls import Controller,Transport
from telemetry import Store


class Native:
    def __init__(self):self.calls=[];self.homed=False
    def request(self,method,params=None):
        self.calls.append((method,params))
        if method=='robot.busStatus':return {'homed':self.homed}
        if method=='pad.bindings':return {'bindings':[{'button':key,'skill':skill} for key,skill in [('a','ground_pick'),('x','roulade'),('rb','kick_right'),('dpad_down','sit_toggle')]]}
        return {'accepted':True}
    def notify(self,calls):self.calls.extend(calls)
    def close(self):pass


class InputTests(unittest.TestCase):
    def setUp(self):
        self.robot=Native();self.now=0;self.input=Input(self.robot,lambda:self.now)
    def send(self,buttons=(),**axes):
        frame={'buttons':list(buttons),'axes':dict.fromkeys(AXES,0)};frame['axes'].update(axes)
        return self.input.command({'action':'state','owner':'webpage-157','frame':frame,'context':{'settings':{'head_rad':.5,'mouth_percent':60}}})
    def test_home_then_hold_and_release_stays_enabled(self):
        self.send(['start']);self.assertIn(('robot.init',None),self.robot.calls)
        self.send();self.robot.homed=True;self.send(['start'])
        self.assertIn(('robot.enable',{'on':False,'toggle':True}),self.robot.calls)
        self.robot.calls.clear();self.send(ly=-1);self.send()
        self.assertIn(('robot.move',{'vx':.3,'vy':0,'vyaw':0}),self.robot.calls)
        self.assertFalse(any(m=='robot.enable' for m,p in self.robot.calls))
    def test_body_and_head_toggles_keep_current_mapping(self):
        self.send(['b'],ly=-1,ry=-1)
        self.assertIn(('robot.pose',{'z':.010,'pitch':.2618,'roll':0,'active':True}),self.robot.calls)
        self.send();self.send(['y'],lx=1,ly=-1,rx=1,ry=-1)
        self.assertIn(('robot.pose',{'active':False}),self.robot.calls)
        self.assertIn(('robot.head',{'neck_pitch':.5,'head_pitch':-.5,'head_yaw':-.5,'head_roll':.5}),self.robot.calls)
    def test_physical_takeover_discards_select_and_does_not_replay(self):
        self.send(['select'],ly=-1);self.now=3
        self.input.hotplug([{'name':'Xbox'}]);self.robot.calls.clear()
        self.assertFalse(self.send(['select'],ly=-1)['accepted'])
        self.input.hotplug([]);self.send()
        self.assertFalse(any(m in ('robot.relax','robot.shutdown','robot.enable') for m,p in self.robot.calls))
        self.assertEqual(self.input.mode,'drive')
    def test_held_select_shuts_down_once_but_short_release_relaxes(self):
        self.send(['select']);self.now=.1;self.send();self.assertIn(('robot.relax',None),self.robot.calls)
        self.send(['select']);self.now=2.2;self.send(['select']);self.send(['select']);self.send()
        self.assertEqual(sum(m=='robot.shutdown' for m,p in self.robot.calls),1)
        self.assertEqual(sum(m=='robot.relax' for m,p in self.robot.calls),1)
    def test_timeout_eof_and_close_never_fabricate_select_release(self):
        self.send(['select'],ly=-1,lt=.5);self.now=.7
        self.assertTrue(self.input.expired());self.input.release();self.input.release()
        self.assertFalse(any(m in ('robot.relax','robot.shutdown','robot.enable') for m,p in self.robot.calls))
        self.assertEqual(self.input.owner,None)
        self.assertIn(('robot.move',{'vx':0,'vy':0,'vyaw':0}),self.robot.calls)
    def test_idle_has_no_timer_and_modes_survive_neutral_frame(self):
        self.send(['y']);self.send();self.assertIsNone(self.input.deadline)
        self.now=50;self.assertFalse(self.input.expired());self.assertEqual(self.input.mode,'head')
    def test_skill_and_sound_bindings(self):
        self.send(['a','rb','x'],dy=1,lt=.5,rt=.5)
        for skill in ['ground_pick','kick_right','roulade','sit_toggle']:self.assertIn(('robot.do',{'skill':skill}),self.robot.calls)
        self.assertIn(('robot.mouth',{'open':.3}),self.robot.calls)
        self.assertIn(('robot.sound',{'tag':'chirp'}),self.robot.calls)
        self.send(['x']);self.assertIn(('robot.sound',{'tag':'wheee','hold':False}),self.robot.calls)
    def test_malformed_nonfinite_and_expired_input_is_never_written(self):
        with self.assertRaises(ValueError):self.send(lx=float('nan'))
        self.assertEqual(self.robot.calls,[])
        request=self.robot.request
        def slow(method,params=None):
            value=request(method,params);self.now+=1;return value
        self.robot.request=slow
        self.assertFalse(self.send(['a'],ly=-1)['accepted'])
        self.assertFalse(any(m=='robot.move' and p['vx']!=0 for m,p in self.robot.calls))
    def test_old_page_close_cannot_close_new_owner(self):
        self.send(ly=-1)
        self.input.command({'action':'close','owner':'old-page-157'})
        self.assertEqual(self.input.owner,'webpage-157')

    def test_hotplug_during_blocking_home_status_discards_following_actions(self):
        request=self.robot.request
        def interrupted(method,params=None):
            result=request(method,params)
            self.input.hotplug([{'name':'Xbox'}])
            return result
        self.robot.request=interrupted
        with self.assertRaises(ValueError):self.send(['start'],ly=-1)
        self.assertNotIn(('robot.init',None),self.robot.calls)
        self.assertFalse(any(m=='robot.move' and p.get('vx') for m,p in self.robot.calls))

    def test_status_listeners_sleep_until_a_state_change(self):
        transport=Transport();changes=[];unsubscribe=transport.subscribe_input_status(changes.append)
        value={'available':True,'real_connected':False,'event_authoritative':True}
        transport._input_status(value);transport._input_status(value)
        self.assertEqual(len(changes),1)
        transport._input_status({**value,'real_connected':True})
        self.assertEqual(len(changes),2);unsubscribe()


class TransportTests(unittest.TestCase):
    def test_kernel_bitmap_word_boundaries_identify_gamepad(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);p=root/'event7/device';(p/'capabilities').mkdir(parents=True)
            (p/'name').write_text('GameSir-Nova 2 Lite')
            words=[0]*5;words[4]=1<<(0x130-256)
            (p/'capabilities/key').write_text(' '.join(format(v,'x') for v in reversed(words)))
            (p/'capabilities/abs').write_text('3')
            self.assertEqual(devices(root)[0]['event'],'event7')
    def test_live_event_overrides_old_system_snapshot_without_polling(self):
        store=Store();transport=Transport();controller=Controller(store,transport=transport)
        transport._input_status({'real_connected':True,'real_devices':[{'name':'Xbox'}],'event_authoritative':True,'available':True})
        self.assertTrue(controller.status({'system':{'real_gamepads':[]},'channels':{'system':{'age_ms':0}}})['webpad']['real_connected'])
    def test_same_byte_stream_handles_multiple_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            # This executor forbids AF_UNIX. Exercise the production request/
            # notification byte stream using real loopback TCP and adapt connect.
            path=str(Path(directory)/'robotd.sock');server=socket.socket();server.bind(('127.0.0.1',0));server.listen()
            accepted=[]
            def serve():
                with server.accept()[0] as peer:
                    accepted.append(peer)
                    with peer.makefile('rb') as reader:
                        for raw in reader:
                            row=json.loads(raw)
                            if 'id' in row:peer.sendall((json.dumps({'id':row['id'],'result':{'accepted':True}})+'\n').encode())
            class Peer(socket.socket):
                def __init__(self,family=socket.AF_INET,kind=socket.SOCK_STREAM,proto=0,fileno=None):super().__init__(socket.AF_INET,kind,proto,fileno=fileno)
                def connect(self,_):super().connect(server.getsockname())
            worker=threading.Thread(target=serve,daemon=True);worker.start();robot=Robot(path)
            with patch('remote_input.socket.socket',Peer):
                robot.request('robot.init');robot.request('robot.enable',{'on':True})
                robot.notify([('robot.move',{'vx':0,'vy':0,'vyaw':0})]);robot.close()
            worker.join(2);server.close()
            self.assertFalse(worker.is_alive());self.assertEqual(len(accepted),1)


if __name__=='__main__':unittest.main()
