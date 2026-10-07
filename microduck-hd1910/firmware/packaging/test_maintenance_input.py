"""Maintenance must finish on a new, verified input connection without motion."""
import tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
import controls
from controls import Controller,Transport,ControlError
from service_control import ServiceController

ROOT=Path(__file__).resolve().parents[1]/'console'

class Store:
    service_operation=True
    def snapshot(self):return {'service_operation':self.service_operation,'bus':{}}
    def record_service_command(self,job):pass

class MaintenanceTests(unittest.TestCase):
    def test_audio_failure_is_read_once_again_after_repair_without_input_activation(self):
        class InlineThread:
            def __init__(self,target,**_):self.target=target
            def start(self):self.target()
        class Maintenance:
            def __init__(self):self.calls=[];self.repaired=False
            def _manage(self,args,privileged):
                self.calls.append(args)
                if not self.repaired:raise RuntimeError('voice setup missing')
                return {'accepted':True,'audio':{'volume':37,'initializing':False}}
        maintenance=Maintenance();transport=Transport();transport.attach_service_transport(maintenance)
        with patch.object(controls.threading,'Thread',InlineThread),patch.object(controls,'open_remote_socket',side_effect=AssertionError('audio recovery activated input')):
            transport.call({'action':'connect'})
            self.assertIn('voice setup missing',transport.audio_status['message'])
            maintenance.repaired=True
            transport.reconnect_after_service()
            for _ in range(20):
                transport.call({'action':'connect'});transport.call({'action':'webpad_status'})
            self.assertEqual(transport.audio_status['volume'],37)
            self.assertEqual(maintenance.calls,[['python3',transport.AUDIO_HELPER,'status']]*2)
        transport.close()

    def test_pre_repair_audio_completion_cannot_overwrite_the_new_generation(self):
        tasks=[]
        class DeferredThread:
            def __init__(self,target,**_):tasks.append(target)
            def start(self):pass
        class Maintenance:
            def _manage(self,*_args,**_kwargs):
                return {'accepted':True,'audio':{'volume':37 if len(tasks)==2 else None}}
        transport=Transport();transport.attach_service_transport(Maintenance())
        with patch.object(controls.threading,'Thread',DeferredThread),patch.object(controls,'open_remote_socket',side_effect=AssertionError('audio recovery activated input')):
            transport.call({'action':'connect'});old=tasks[0]
            transport.reconnect_after_service();fresh=tasks[1]
            fresh();self.assertEqual(transport.audio_status['volume'],37)
            tasks.pop();old()
            self.assertEqual(transport.audio_status['volume'],37,'late obsolete status may not restore unknown volume')
        transport.close()

    def test_completed_upgrade_retires_old_stream_without_activating_webpad(self):
        class Peer:
            closed=False
            def close(self):self.closed=True
        transport=Transport();controller=Controller(Store(),transport=transport);old=Peer();transport.peer=old
        transport.pad_status={'available':False,'error':'old socket missing'}
        with patch.object(controls,'open_remote_socket',side_effect=AssertionError('maintenance activated webpad')):
            answer=controller.reconnect_after_service()
        self.assertTrue(answer['webpad_reconnected']);self.assertTrue(old.closed)
        self.assertIsNone(transport.peer);self.assertTrue(controller.status()['webpad']['available'])
        self.assertNotIn('error',controller.status()['webpad'])

    def test_completed_upgrade_reconnects_input_without_readiness_gate(self):
        class Firmware:
            def upgrade(self,*_,**kwargs):kwargs['progress']('files installed\n');return {'models_verified':True}
        class Input:
            def __init__(self,ready):self.ready=ready;self.calls=[]
            def resume_connections(self):pass
            def reconnect_after_service(self):
                self.calls.append('status-only')
                if not self.ready:raise ControlError('网页手柄接口未启动',503)
                return {'webpad_reconnected':True,'available':True}
        for ready in (True,False):
            with self.subTest(ready=ready):
                store=Store();input=Input(ready);service=ServiceController(store,transport=Firmware(),controls=input)
                job={'action':'upgrade-service','status':'running'}
                service._execute({'action':'upgrade-service','supported':True,'firmware':'bundled'},job,0)
                deadline=time.monotonic()+2
                while job.get('result',{}).get('input',{}).get('status') not in ('ready','error') and time.monotonic()<deadline:time.sleep(.01)
                self.assertEqual(input.calls,['status-only']);self.assertFalse(store.service_operation)
                self.assertEqual(job['status'],'completed')
                self.assertEqual(job['result']['input']['webpad_reconnected'],ready)
                if not ready:self.assertIn('接口未启动',job['result']['input']['error'])

    def test_failed_local_handshake_exposes_actual_unavailable_state(self):
        class Input:
            connected=True;audio_status={};pad_status={}
            def reconnect_after_service(self):return {'accepted':False,'reason':'input.sock missing'}
        controller=Controller(Store(),transport=Input())
        with self.assertRaisesRegex(ControlError,'input.sock missing'):controller.reconnect_after_service()
        self.assertIn('input.sock missing',controller.status()['error'])
        self.assertFalse(controller.status()['webpad']['available'])

if __name__=='__main__':unittest.main()
