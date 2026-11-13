"""Regressions for the 2026-10-23 user log; real worker pipes, fake cloud."""
import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from ai_action_gate import ActionDenied
from ai_doubao import DoubaoNative
from ai_runtime import AIHub
from verification.test_ai_hat import Hub


def run_worker(case,worker_source=None):
    """Leave stdin open when the provider returns: the original fatal trigger."""
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        (root/'ai_zero.py').write_bytes(Path(worker_source or ROOT/'ai_zero.py').read_bytes())
        (root/'ai_input_lease.py').write_bytes((ROOT/'ai_input_lease.py').read_bytes())
        (root/'ai_voices.py').write_bytes((ROOT/'ai_voices.py').read_bytes())
        (root/'ai_persona.py').write_bytes((ROOT/'ai_persona.py').read_bytes())
        (root/'ai_vision.py').write_bytes((ROOT/'ai_vision.py').read_bytes())
        (root/'ai_hat_audio.py').write_text('def hat_device():return None\n')
        provider='''import time
class DoubaoNative:
 def __init__(self,hub,key,voice,input_device,output_device,stop):self.stop=stop
 def run(self):
  time.sleep(.1)
  if CASE != 'return':self.stop.wait(5)
 def close(self):self.stop.set()
'''.replace('CASE',repr(case))
        (root/'ai_doubao.py').write_text(provider)
        proc=subprocess.Popen([sys.executable,'-u',str(root/'ai_zero.py')],
                              stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            config={'api_key':'fixture-secret','voice_id':'fixture','tools':[]}
            message=json.dumps(config).encode()+b'\n'
            if case=='stop':message+=b'{"action":"stop"}\n'
            proc.stdin.write(message);proc.stdin.flush()
            if case=='eof':proc.stdin.close()
            proc.wait(timeout=4)
            return proc.returncode,proc.stdout.read().decode(),proc.stderr.read().decode()
        finally:
            if proc.poll() is None:proc.kill();proc.wait()
            for pipe in (proc.stdin,proc.stdout,proc.stderr):pipe.close()


class ZeroShutdownTests(unittest.TestCase):
    def test_provider_return_stop_and_eof_exit_cleanly(self):
        for case in ('return','stop','eof'):
            with self.subTest(case=case):
                code,stdout,stderr=run_worker(case)
                self.assertEqual(code,0,stderr)
                self.assertNotIn('_enter_buffered_busy',stderr)
                events=[json.loads(line) for line in stdout.splitlines()]
                self.assertEqual(events[-1]['kind'],'zero_stopped')


class SpeechSessionTests(unittest.TestCase):
    def test_pending_tool_thread_is_released_before_worker_shutdown(self):
        from ai_zero import ZeroHub
        stop=threading.Event();hub=ZeroHub({'api_key':'fixture','tools':[]},stop)
        waiting=threading.Event();events=[]
        def log(kind,**fields):
            events.append({'kind':kind,**fields})
            if kind=='action_request':waiting.set()
        hub.log=log
        p=DoubaoNative(hub,'fixture','fixture',None,None,stop)
        p._handle({'type':'response.function_call_arguments.done','items':[
            {'name':'stay_silent','arguments':'{}','call_id':'pending'}]})
        self.assertTrue(waiting.wait(1))
        p.close()
        self.assertFalse(p.tool_threads)
        self.assertTrue(any(e['kind']=='tool_feedback' for e in events))

    def test_revised_asr_hypotheses_do_not_repeat_and_final_is_authoritative(self):
        hub=Hub();p=DoubaoNative(hub,'fixture','fixture',None,None,threading.Event())
        words=['你','你好','你好。','你好','你好。']
        for word in words:
            p._handle({'type':'conversation.item.input_audio_transcription.delta',
                       'item_id':'user-log','delta':word})
        self.assertEqual([e['text'] for e in hub.events if e['kind']=='transcript'],words)
        p._handle({'type':'conversation.item.input_audio_transcription.completed',
                   'item_id':'user-log','transcript':'你好。'})
        self.assertEqual(hub.events[-1]['text'],'你好。')
        self.assertTrue(hub.events[-1]['final'])
        self.assertFalse(p.asr_partial)

    def test_locked_text_and_audio_are_blocked_but_next_turn_can_use_tools(self):
        hub=Hub();p=DoubaoNative(hub,'fixture','fixture',None,None,threading.Event())
        sent=[];p._send=sent.append
        for part in ['（','保持安静','）']:
            p._handle({'type':'response.output_text.delta','item_id':'r1','delta':part})
        p._handle({'type':'response.output_text.done','item_id':'r1','text':'（保持安静）'})
        for _ in range(3):
            p._handle({'type':'response.output_audio.delta','delta':base64.b64encode(b'\0'*640).decode()})
        self.assertFalse(p.stop_event.is_set())
        self.assertTrue(p.audio_queue.empty())
        self.assertFalse(hub.gate.speaking_enabled)
        self.assertEqual(len([e for e in hub.events if e['kind']=='model_violation']),2)
        p._handle({'type':'response.done'})
        p._handle({'type':'conversation.item.input_audio_transcription.completed','transcript':'点点头'})
        p._tool_calls({'items':[{'name':'head_expression','arguments':'{"gesture":"nod"}','call_id':'next-turn'}]})
        self.assertTrue(any(method=='robot.head' for method,_ in hub.robot.calls))
        self.assertTrue(hub.events[-1]['result']['accepted'])
        self.assertFalse(p.stop_event.is_set())
        self.assertFalse(hub.gate.speaking_enabled)


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.snap={'service_sample_fresh':True,'service_sample_age_ms':15,
            'bus':{'mode':'motion','phase':'control','homed':True,'policy_enabled':True,
                   'sitting':False,'torque_off_pending':False,
                   'native':{'torque_state_confirmed':True,'imu_ready':True}}}
        self.pad={}
        self.hub=AIHub(SimpleNamespace(peek=lambda:self.snap),
            controller=SimpleNamespace(status=lambda _: {'webpad':self.pad}),
            connection=SimpleNamespace(active=True))
        self.hub.gate.set_skills({'skills':[{'name':'flamingo'}],'built_in':[]})
        self.sent=[]
        self.hub.gate.rpc=lambda method,args:self.sent.append((method,args)) or {'accepted':True}
        # Model completion now comes from the existing native policy stream.
        from verification.test_ai_v200 import FakeClock
        clock=FakeClock();self.hub.gate.clock=clock;self.hub.gate.sleep=clock.sleep
        base=self.hub.gate.state
        self.hub.gate.monitor=lambda:{**base(),'state_fresh':True,'state_t_ns':round(clock()*1e9),
                                     'policy':'flamingo' if self.sent and clock()<50.25 else 'walk'}

    def tearDown(self):self.hub.close()

    def test_stale_feedback_is_identified_without_false_home_instruction(self):
        self.snap.update(service_sample_fresh=False,service_sample_age_ms=720)
        with self.assertRaisesRegex(ActionDenied,'实时反馈.*720') as caught:
            self.hub.gate.execute('perform_skill',{'skill':'flamingo'})
        self.assertNotIn('HOME',str(caught.exception))
        denial=self.hub.events[-1]
        self.assertEqual(denial['kind'],'tool_denied')
        self.assertTrue(denial['state']['readback']['homed'])
        self.assertFalse(denial['state']['fresh'])
        self.assertFalse(self.sent)

    def test_each_original_motion_check_remains_required_and_is_named(self):
        for owner,key,value,reason in (
            ('bus','mode','commissioning','运动模式'),('bus','phase','homing','控制阶段'),
            ('bus','homed',False,'尚未 HOME'),('bus','policy_enabled',False,'策略未启用'),
            ('native','torque_state_confirmed',False,'力矩未使能'),
            ('native','imu_ready',False,'IMU 未就绪'),('bus','torque_off_pending',True,'等待卸力')):
            state=self.snap['bus']['native'] if owner=='native' else self.snap['bus']
            old=state[key];state[key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ActionDenied,reason):
                self.hub.gate.execute('perform_skill',{'skill':'flamingo'})
            state[key]=old
        self.assertFalse(self.sent)
        self.assertTrue(self.hub.gate.execute('perform_skill',{'skill':'flamingo'})['accepted'])
        self.assertEqual(self.sent,[('robot.do',{'skill':'flamingo'})])

    def test_only_active_webpad_owner_blocks_ai_not_connected_physical_gamepad(self):
        self.pad={'owner':'web-client','real_connected':True}
        with self.assertRaisesRegex(ActionDenied,'网页手柄'):
            self.hub.gate.execute('perform_skill',{'skill':'flamingo'})
        self.assertFalse(self.sent)
        self.pad={'real_connected':True}
        self.assertEqual(self.hub.gate.execute('perform_skill',{'skill':'flamingo'})['status'],'completed')
        self.assertEqual(self.sent,[('robot.do',{'skill':'flamingo'})])


if __name__=='__main__':unittest.main()
