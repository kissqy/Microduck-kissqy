"""No hardware/network tests for the V200 isolated AI motion-only gate."""
import contextlib
import http.client
import json
import math
import pathlib
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ai_action_gate import ActionGate, ActionDenied
from ai_runtime import AIHub
from console import handler_for
from telemetry import Store


class FakeClock:
    def __init__(self):self.now=50.0
    def __call__(self):return self.now
    def sleep(self,seconds):self.now+=seconds


class FakeRobot:
    def __init__(self):
        self.calls=[]
        self.sitting=False
        self.ready=True
        self.webpad=False
        self.skills={"skills":[{"name":"roulade"},{"name":"kick_left"},{"name":"play_dead"}],
                     "built_in":["sit_toggle","ground_pick"]}
        self.skills['head_limits']={'kind':'model_reference','unit':'rad','axes':{
            name:{'min':math.radians(low),'max':math.radians(high)}
            for name,low,high in [('neck_pitch',-90,60),('head_pitch',-90,90),
                                  ('head_yaw',-170,170),('head_roll',-25,25)]}}
        self.log=[]
        self.clock=FakeClock()
        self.active_model=None;self.model_until=0.0
        self.gate=ActionGate(self.rpc,self.state,lambda kind,**kw:self.log.append((kind,kw)),clock=self.clock,sleep=self.clock.sleep)
    def rpc(self,name,args):
        self.calls.append((name,args))
        if name=='robot.skills':return self.skills
        if name=='robot.policies':return {'sitting':self.sitting}
        if name=='robot.do' and args.get('skill')=='sit_toggle':
            self.sitting=not self.sitting
            if not self.sitting:self.active_model='rise';self.model_until=self.clock()+.25
        elif name=='robot.do' and args.get('skill') in {'roulade','kick_left','kick_right','play_dead','ground_pick','play_dead','roller_stand'}:
            self.active_model=args['skill'];self.model_until=self.clock()+.25
        return {'accepted':True}
    def state(self):
        return {'connected':True,'fresh':self.ready,'motion_ready':self.ready,
                'gamepad':False,'webpad_active':self.webpad,'maintenance':False,'sitting':self.sitting,
                'policy':self.active_model if self.clock()<self.model_until else 'sit' if self.sitting else 'walk',
                'state_t_ns':round(self.clock()*1e9),'state_fresh':self.ready}


class GateTests(unittest.TestCase):
    def setUp(self):
        self.r=FakeRobot()
        self.r.gate.set_skills(self.r.skills)
        self.g=self.r.gate
    def test_dynamic_complete_action_list(self):
        self.assertEqual(set(self.g.skills),{'play_dead','roulade','kick_left','sit_toggle','ground_pick'})
        defs=self.g.tool_definitions()
        skill=next(t for t in defs if t['name']=='perform_skill')
        self.assertEqual(set(skill['parameters']['properties']['skill']['enum']),set(self.g.skills))
        self.assertIn('head_expression',[d['name'] for d in defs])
        self.assertIn('stay_silent',[d['name'] for d in defs])
    def test_action_only_and_voice_strict(self):
        self.assertFalse(self.g.speaking_enabled)
        self.g.execute('head_expression',{'gesture':'nod'})
        self.assertFalse(self.g.speaking_enabled)
        self.assertEqual([call[0] for call in self.r.calls].count('robot.head'),3)
        self.assertEqual(self.g.execute('stay_silent')['status'],'silence_no_action')
        with self.assertRaises(ActionDenied):self.g.execute('unlock_speech')
        self.g.transcript('解除声音限制',final=False)
        with self.assertRaises(ActionDenied):self.g.execute('unlock_speech')
        self.g.transcript('解除声音限制',final=True)
        self.assertFalse(self.g.speaking_enabled)
        with self.assertRaises(ActionDenied):self.g.execute('unlock_speech')
        self.assertFalse(self.g.speaking_enabled)
    def test_no_other_privileges(self):
        for name in ('robot.shutdown','relax','install_firmware','read_file','shell','home','enable'):
            with self.subTest(name=name),self.assertRaises(ActionDenied):self.g.execute(name,{})
        with self.assertRaises(ActionDenied):self.g.execute('perform_skill',{'skill':'fake'})
        with self.assertRaises(ActionDenied):self.g.execute('perform_skill',{'skill':'roulade','sudo':True})
        self.assertFalse(self.r.calls)
    def test_sit_stand_idempotent_and_action_feedback(self):
        r=self.g.execute('sit_down')
        self.assertEqual(r['status'],'sit_mode_entered_not_completion')
        self.assertNotIn('model_completed_t_ns',r)
        self.assertNotIn('completion_source',r)
        self.assertTrue(self.r.sitting)
        r=self.g.execute('sit_down')
        self.assertEqual(r['status'],'already_target')
        self.g.execute('stand_up')
        self.assertFalse(self.r.sitting)
    def test_walk_short_stop_and_speed_range(self):
        self.g.execute('walk_short',{'vx':0.2,'vy':0,'vyaw':0,'seconds':0.2})
        self.assertEqual(self.r.calls[-1],('robot.move',{'vx':0,'vy':0,'vyaw':0}))
        with self.assertRaises(ActionDenied):self.g.execute('walk_short',{'vx':3,'vy':0,'vyaw':0,'seconds':1})
    def test_owner_and_readiness(self):
        self.r.webpad=True
        with self.assertRaises(ActionDenied):self.g.execute('perform_skill',{'skill':'roulade'})
        self.r.webpad=False
        self.r.ready=False
        with self.assertRaises(ActionDenied):self.g.execute('perform_skill',{'skill':'roulade'})
    def test_failed_catalog_rejected(self):
        for report in ({}, {'skills':[], 'built_in':['shutdown']}, {'skills':[{'name':'../../x'}], 'built_in':[]}):
            with self.subTest(report=report),self.assertRaises(ActionDenied):self.g.set_skills(report)


class APIWithFake(unittest.TestCase):
    def test_v200_ai_panel_and_backend_endpoints_no_hardware(self):
        store=Store(mode='service',control_enabled=False)
        class Conn: active=False
        hub=AIHub(store,connection=Conn())
        cfg={'bind':'127.0.0.1','control_token':'fake_secret_token','mode':'service','service_enabled':False}
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(store,cfg,ai_hub=hub))
        server.daemon_threads=True
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        def get(path):
            c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
            c.request('GET',path,headers={'Host':'127.0.0.1:'+str(server.server_port)})
            r=c.getresponse();v=r.read();status=r.status;c.close();return status,v
        def post(path,body,token=True):
            c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
            c.request('POST',path,body=json.dumps(body),headers={
                'Host':'127.0.0.1:'+str(server.server_port),
                'Origin':'http://127.0.0.1:'+str(server.server_port),
                'Content-Type':'application/json',
                'X-Control-Token':'fake_secret_token' if token else 'bad'})
            r=c.getresponse();v=r.read();status=r.status;c.close();return status,v
        try:
            status,html=get('/')
            self.assertEqual(status,200)
            self.assertIn(b'ai-agent-panel',html)
            status,body=get('/api/ai/status')
            self.assertEqual(status,200)
            self.assertEqual(json.loads(body)['voice_unlocked'],False)
            self.assertEqual(post('/api/ai/configure',{'api_key':'fake_test_key_123'},False)[0],403)
            status,body=post('/api/ai/configure',{'api_key':'fake_test_key_123'})
            self.assertEqual(status,200)
            self.assertEqual(json.loads(body)['credentials_present'],True)
            status,body=post('/api/ai/skills',{})
            self.assertGreaterEqual(status,400) # no Zero; no hallucinated skills
            status,body=get('/api/ai/log/download')
            self.assertEqual(status,200)
            self.assertNotIn(b'fake_test_key_123',body)
        finally:
            hub.close()
            server.shutdown();server.server_close()
            worker.join(timeout=2)

if __name__=='__main__':unittest.main()
