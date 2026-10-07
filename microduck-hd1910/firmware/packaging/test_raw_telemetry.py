"""Exercise the real raw relay, bounded fan-out and browser/Python adapters."""
import base64
import copy
import importlib.util
from http.server import ThreadingHTTPServer
import io
import json
import math
import os
from pathlib import Path
import queue
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'console'))
import raw_telemetry as raw
from telemetry import Store, IDS, NAMES, LABELS, BASELINE, VERSION


def tree(value):
    if value is None: return b'\0'
    if value is False: return b'\1'
    if value is True: return b'\2'
    if isinstance(value, int): return bytes((3 if value < 0 else 4,)) + struct.pack('<q' if value < 0 else '<Q', value)
    if isinstance(value, float): return b'\5' + struct.pack('<d', value)
    if isinstance(value, str):
        data = value.encode(); return b'\6' + struct.pack('<I',len(data)) + data
    if isinstance(value, list): return b'\7' + struct.pack('<I',len(value)) + b''.join(map(tree,value))
    if isinstance(value, dict):
        return b'\10' + struct.pack('<I',len(value)) + b''.join(tree(key)[1:] + tree(item) for key,item in value.items())
    raise TypeError(type(value))


def frame(kind, value):
    payload = bytes((kind,)) + (json.dumps(value,ensure_ascii=False,allow_nan=False).encode() if kind in (1,3) else tree(value))
    return struct.pack('<I',len(payload)) + payload


class RawTelemetryTests(unittest.TestCase):
    def test_codec_handles_nonfinite_as_missing_and_rejects_structural_errors(self):
        value={'zero':0,'negative':-999,'maximum':2**64-1,'minimum':-2**63,'text':'原始\n遥测','array':[False,True,None,1.5]}
        encoded=tree(value)
        self.assertEqual(raw.decode_tree(encoded),value)
        for size in range(len(encoded)):
            with self.assertRaises(ValueError): raw.decode_tree(encoded[:size])
        self.assertEqual(raw.decode_tree(tree({'nan':float('nan'),'inf':float('inf'),'negative_inf':float('-inf')})),{'nan':None,'inf':None,'negative_inf':None})
        for invalid in (encoded+b'\0',b'\10\xff\xff\xff\xff',b'\x09',b'\10\2\0\0\0'+tree('x')[1:]+tree(1)+tree('x')[1:]+tree(2)):
            with self.assertRaises(ValueError):raw.decode_tree(invalid)

    def test_mirror_preserves_complete_reports_at_ten_hz_without_skipping_low_rate_channels(self):
        events=[]; mirror=raw.Mirror(events.append)
        with patch.object(raw.time,'monotonic',return_value=100):
            mirror.accept(frame(1,{'schema':'r17.raw.v1','channels':{'bus':{'build':'test','native':{'imu_mount_verified':True}}},'calibration':{'calibration':{'joints':[]}},'capabilities':{'accepted':True}}))
            mirror.accept(frame(2,{'state':{'joints':[0]},'bus':{'cycle':1,'native':{'joints':[{'id':20,'name':'x'}]}}}))
            mirror.accept(frame(2,{'state':{'joints':[2]},'bus':{'cycle':2}}))
            mirror.accept(frame(4,{'system':{'cpu_temp_c':85},'health':{'ready':True}}))
        self.assertEqual([e['channel'] for e in events],['calibration','capabilities','state','bus','system','health'])
        self.assertEqual(events[3]['data'],{'build':'test','cycle':1,'native':{'imu_mount_verified':True,'joints':[{'id':20,'name':'x'}]}})
        with patch.object(raw.time,'monotonic',return_value=100.1):mirror.accept(frame(2,{'bus':{'cycle':3}}))
        self.assertNotIn('joints',events[-1]['data']['native'],'Missing dynamic samples must never inherit the previous frame')

    def test_uniform_execution_metadata_actual_values_and_clear_reach_both_stores_and_recording(self):
        # Fixed model metadata and actual scale/filter samples remain distinct.
        # Stopping inference or replacing the model must clear old live output.
        sha='9'*64
        profile={'schema':'microduck-runtime-execution/v1','mode':'uniform','model_sha256':sha,
                 'action_scale':.9,'head_lowpass':.5,'legs_lowpass':.7}
        model={'sha256':sha,'task':'Mjlab-VelStand-Rough-Backlash-MicroDuck','runtime_execution_profile':profile}
        base={'mode':'motion','build':'fixture','loaded_models':{'walk':model},'active_model':model,'native':{'sample_age_ms':1}}
        records=[frame(1,{'schema':'r17.raw.v1','channels':{'bus':base}})]
        for cycle,actual in enumerate((.945,.9,None),1):
            records.append(frame(2,{'bus':{'cycle':cycle,'policy_enabled':actual is not None,
                'active_action_scale':actual,'active_target_filters':None if actual is None else {'head_lowpass':.5,'legs_lowpass':.7},
                'scale_use':'held' if actual is None else 'joint_uniform'}}))
        ordinary={'sha256':'8'*64,'task':'Mjlab-Velocity-Rough-Backlash-MicroDuck'}
        records.append(frame(1,{'schema':'r17.raw.v1','channels':{'bus':{**base,'loaded_models':{'walk':ordinary},'active_model':ordinary}}}))
        records.append(frame(2,{'bus':{'cycle':4,'policy_enabled':True,'active_action_scale':.735,
            'active_target_filters':{'head_lowpass':.44,'legs_lowpass':.66},'scale_use':'walking'}}))
        events=[];mirror=raw.Mirror(events.append)
        store=Store('service',control_enabled=True);expected=[]
        for index,record in enumerate(records):
            with patch.object(raw.time,'monotonic',return_value=100+index*.1):mirror.accept(record)
            if record[4]!=2:continue
            event=events[-1];store.ingest(event)
            expected.append(copy.deepcopy(store.peek()['bus']))
        self.assertEqual(expected[0]['loaded_models']['walk']['runtime_execution_profile'],profile)
        self.assertEqual([item['active_action_scale'] for item in expected],[.945,.9,None,.735])
        self.assertEqual([item['active_target_filters'] for item in expected],[{'head_lowpass':.5,'legs_lowpass':.7},{'head_lowpass':.5,'legs_lowpass':.7},None,{'head_lowpass':.44,'legs_lowpass':.66}])
        self.assertNotIn('runtime_execution_profile',expected[-1]['active_model'])
        config={'mode':'service','control_enabled':True,'ids':IDS,'names':NAMES,'labels':LABELS,'version':VERSION,'baseline':BASELINE}
        with tempfile.TemporaryDirectory() as directory:
            temp=Path(directory);(temp/'package.json').write_text('{"type":"module"}')
            for name in ('raw-telemetry.js','raw-kinematics.js','service-builds.js'):shutil.copyfile(ROOT/'console/static'/name,temp/name)
            script="""import assert from 'node:assert/strict';
import {TelemetryStore} from './raw-telemetry.js';
let text='';for await(const part of process.stdin)text+=part;const input=JSON.parse(text);
let now=100;const store=new TelemetryStore(input.config,()=>now,()=>1700000000+now),actual=[];
for(const record of input.records){now+=.1;store.accept(new Uint8Array(record));if(record[4]===2)actual.push(store.snapshot().bus);}
assert.deepEqual(actual,input.expected);
assert.deepEqual(store.recording().frames.map(frame=>frame.bus),input.expected);
console.log('PASS uniform metadata, actual values and null clear survive browser snapshots and recording');
"""
            (temp/'test.mjs').write_text(script)
            result=subprocess.run(['node',str(temp/'test.mjs')],input=json.dumps({'config':config,'records':[list(record) for record in records],'expected':expected}),text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)

    def test_fanout_preserves_bytes_bounds_backlog_and_never_replays_old_measurements_as_fresh(self):
        hub=raw.Hub();first=hub.subscribe();first.get_nowait()
        meta=frame(1,{'schema':'r17.raw.v1','channels':{}});sample=frame(2,{'state':{'t':1}})
        hub.raw(meta);hub.raw(sample)
        self.assertEqual(first.get_nowait(),(2,meta));self.assertEqual(first.get_nowait(),(2,sample))
        second=hub.subscribe();second.get_nowait();self.assertEqual(second.get_nowait(),(2,meta));self.assertTrue(second.empty())
        ended=[];first.close_stream=lambda:ended.append(True)
        for _ in range(129):hub.raw(sample)
        self.assertEqual(ended,[True]);self.assertIsNone(first.get_nowait());self.assertNotIn(first,hub.clients)
        hub.reset();fresh=hub.subscribe();fresh.get_nowait();hub.raw(sample,0);hub.event({'channel':'state','error':'old'},0)
        self.assertTrue(fresh.empty(),'A retired SSH generation cannot refill the new connection')

    def test_native_stream_and_tof_are_forwarded_byte_for_byte_through_actual_production_loop(self):
        channels={};received={};stop=threading.Event();hub=raw.Hub();browser=hub.subscribe();browser.get_nowait();events=[]
        raw_frames=[frame(1,{'schema':'r17.raw.v1','channels':{},'capabilities':{'accepted':True}}),frame(2,{'state':{'joints':[.1]},'bus':{'cycle':1}}),frame(4,{'system':{'cpu_temp_c':88}})]
        tof_messages=[{'jsonrpc':'2.0','id':1,'result':{'accepted':True,'rows':8,'cols':8}},{'jsonrpc':'2.0','method':'tof.frame','params':{'seq':5,'rows':8,'cols':8,'distance_mm':[10]*64,'status':[5]*64}}]
        def remote(target,path,system_log=None,timeout=10,stop=None):
            client,server=socket.socketpair();channels[path]=(client,server)
            def daemon():
                request=b''
                while not request.endswith(b'\n'):request+=server.recv(1)
                received[path]=json.loads(request)
                if path=='robot':
                    wire=json.dumps({'id':1,'result':{'accepted':True,'schema':'r17.raw.v1','framing':'u32le'}}).encode()+b'\n'+b''.join(raw_frames)
                else:wire=b''.join(json.dumps(m,separators=(',',':')).encode()+b'\n' for m in tof_messages)
                # Split through the length header, typed scalar and UTF-8 payload.
                for start in range(0,len(wire),7):server.sendall(wire[start:start+7])
                stop.wait(3)
                server.close()
            threading.Thread(target=daemon,daemon=True).start()
            return client
        with patch('socket_transport.open_remote_socket',remote):
            worker=threading.Thread(target=raw.raw_loop,args=('duck',{'hub':hub,'robotd_socket':'robot','tofd_socket':'tof'},events.append,stop),daemon=True);worker.start()
            try:
                output=[];until=time.monotonic()+3
                while len(output)<5 and time.monotonic()<until:
                    opcode,payload=browser.get(timeout=3)
                    if opcode==2:output.append(payload)
                self.assertEqual([p for p in output if p[4]!=3],raw_frames)
                self.assertEqual([p[5:] for p in output if p[4]==3],[json.dumps(m,separators=(',',':')).encode()+b'\n' for m in tof_messages])
                self.assertEqual(received['robot']['method'],'robot.rawSubscribe');self.assertEqual(received['tof']['method'],'tof.stream')
                self.assertEqual({e['channel'] for e in events},{'capabilities','state','bus','system','tof'})
            finally:stop.set();worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertTrue(all(client.fileno()==-1 for client,_ in channels.values()))

    def test_ssh_authentication_failure_is_reported_without_killing_the_collector(self):
        events=[];stop=threading.Event();hub=raw.Hub()
        with patch('socket_transport.open_remote_socket',side_effect=raw.SSHConnectError('Permission denied')):
            worker=threading.Thread(target=raw.raw_loop,args=('duck',{'hub':hub,'robotd_socket':'robot','tofd_socket':'tof'},events.append,stop),daemon=True);worker.start()
            limit=time.monotonic()+1
            while not any(e['channel']=='state' for e in events) and time.monotonic()<limit:time.sleep(.005)
            self.assertTrue(worker.is_alive(),'The live connection can retry after an SSH login/network failure')
            stop.set();worker.join(2)
        self.assertEqual({e['channel'] for e in events},set(raw.TTL))
        self.assertTrue(all('Permission denied' in e['error'] for e in events))
        self.assertFalse(worker.is_alive())

    def test_tof_quiet_ack_refreshes_once_and_a_real_frame_rearms_the_next_quiet_period(self):
        class FastStop(threading.Event):
            def wait(self, timeout=None):return super().wait(.02 if timeout==2 else timeout)
        stop=FastStop();hub=raw.Hub();events=[];tof=[];servers=[]
        def remote(target,path,*_,**kwargs):
            client,server=socket.socketpair();servers.append(server)
            def daemon():
                request=b''
                while not request.endswith(b'\n'):request+=server.recv(1)
                if path=='robot':
                    server.sendall(b'{"id":1,"result":{"accepted":true,"schema":"r17.raw.v1","framing":"u32le"}}\n'+frame(1,{'schema':'r17.raw.v1','channels':{}}))
                else:
                    tof.append(server)
                    server.sendall(json.dumps({'id':1,'result':{'accepted':True,'reason':'starting' if len(tof)==1 else 'sensor unavailable'}}).encode()+b'\n')
                stop.wait(5)
            threading.Thread(target=daemon,daemon=True).start();return client
        def wait_for(predicate,timeout=2):
            deadline=time.monotonic()+timeout
            while not predicate() and time.monotonic()<deadline:time.sleep(.005)
            self.assertTrue(predicate())
        with patch('socket_transport.open_remote_socket',remote),patch.object(raw,'TOF_IDLE_SECONDS',.04):
            worker=threading.Thread(target=raw.raw_loop,args=('duck',{'hub':hub,'robotd_socket':'robot','tofd_socket':'tof'},events.append,stop),daemon=True);worker.start()
            try:
                wait_for(lambda:len(tof)>=2);time.sleep(.65)
                self.assertEqual(len(tof),2,'A quiet sensor must not accumulate a new subscriber every timeout')
                self.assertFalse(any('error' in e for e in events),'An accepted quiet ToF preserves its availability reason')
                tof[-1].sendall(b'{"method":"tof.frame","params":{"seq":1,"rows":8,"cols":8}}\n')
                wait_for(lambda:len(tof)>=3);time.sleep(.65);self.assertEqual(len(tof),3)
                self.assertTrue(any(e.get('data',{}).get('seq')==1 for e in events))
                self.assertEqual([e['data']['subscription']['reason'] for e in events if 'subscription' in e.get('data',{})],['starting','sensor unavailable','sensor unavailable'])
            finally:
                stop.set();worker.join(2)
                for server in servers:server.close()
            self.assertFalse(worker.is_alive())

    def test_server_websocket_frame_lengths_support_full_raw_metadata(self):
        for size in (1,125,126,65535,65536,131072):
            out=io.BytesIO();raw.send_frame(out,2,b'x'*size);data=out.getvalue();self.assertEqual(data[0],130)
            if size<126:self.assertEqual(data[1],size);header=2
            elif size<65536:self.assertEqual(struct.unpack('!H',data[2:4])[0],size);header=4
            else:self.assertEqual(struct.unpack('!Q',data[2:10])[0],size);header=10
            self.assertEqual(data[header:],b'x'*size)

    def test_real_websocket_auth_fanout_ping_and_close_do_not_disconnect_robot(self):
        from console import handler_for
        store=Store('service');store.raw_hub=raw.Hub();store.record_service_command({'action':'capture','status':'completed'})
        cfg={'bind':'127.0.0.1','control_token':'telemetry-token','service_enabled':True}
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(store,cfg));server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.02},daemon=True);thread.start()
        streams=[]
        def connect(token='telemetry-token',origin=None):
            sock=socket.create_connection(server.server_address,timeout=3);streams.append(sock);reader=sock.makefile('rb');streams.append(reader)
            host='127.0.0.1:'+str(server.server_port)
            request=(f'GET /api/telemetry/socket HTTP/1.1\r\nHost: {host}\r\nOrigin: {origin or "http://"+host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: '+base64.b64encode(b'0123456789abcdef').decode()+f'\r\nSec-WebSocket-Protocol: r17-telemetry, r17-auth.{token}\r\n\r\n')
            sock.sendall(request.encode());status=reader.readline()
            while reader.readline() not in (b'\r\n',b''):pass
            return sock,reader,status
        def read(reader):
            head=reader.read(2);self.assertEqual(len(head),2);size=head[1]&127
            if size==126:size=struct.unpack('!H',reader.read(2))[0]
            elif size==127:size=struct.unpack('!Q',reader.read(8))[0]
            return head[0]&15,reader.read(size)
        def until(reader,opcode):
            for _ in range(20):
                kind,payload=read(reader)
                if kind==opcode:return payload
            self.fail('WebSocket frame did not arrive')
        def client_frame(sock,opcode,payload=b''):
            mask=b'abcd';sock.sendall(bytes((128|opcode,128|len(payload)))+mask+bytes(v^mask[i%4] for i,v in enumerate(payload)))
        try:
            _,_,denied=connect(token='wrong');self.assertIn(b'403',denied)
            _,_,denied=connect(origin='http://attacker.invalid');self.assertIn(b'403',denied)
            a,ar,accepted=connect();self.assertIn(b'101',accepted)
            b,br,accepted=connect();self.assertIn(b'101',accepted)
            for reader in (ar,br):
                self.assertIn('reset',json.loads(until(reader,1)),'Reset must precede the first auxiliary delta')
                aux=json.loads(until(reader,1));self.assertEqual(aux['generation'],store.raw_hub.generation)
                self.assertEqual(aux['aux']['service_commands'][0]['action'],'capture')
            data=frame(2,{'state':{'t':1},'bus':{'cycle':1}});store.raw_hub.raw(data)
            self.assertEqual(until(ar,2),data);self.assertEqual(until(br,2),data)
            client_frame(a,9,b'ping');self.assertEqual(until(ar,10),b'ping')
            before=store.raw_hub.generation;client_frame(a,8,struct.pack('!H',1000));self.assertEqual(until(ar,8),struct.pack('!H',1000))
            limit=time.monotonic()+1
            while len(store.raw_hub.clients)!=1 and time.monotonic()<limit:time.sleep(.005)
            self.assertEqual(len(store.raw_hub.clients),1);self.assertEqual(store.raw_hub.generation,before);self.assertFalse(store.connection_paused.is_set())
            store.raw_hub.raw(data);self.assertEqual(until(br,2),data)
            client_frame(b,8,struct.pack('!H',1000));until(br,8)
        finally:
            for stream in streams:stream.close()
            server.shutdown();server.server_close();thread.join(1)

    def test_production_rust_worker_fixture_matches_both_decoders_and_preserves_15_joints(self):
        wire=(ROOT/'packaging/fixtures/raw-telemetry-v1.bin').read_bytes()
        expected=json.loads((ROOT/'packaging/fixtures/raw-telemetry-v1.json').read_text())
        mirror_events=[];mirror=raw.Mirror(mirror_events.append);frames=[];offset=0
        while offset<len(wire):
            size=struct.unpack_from('<I',wire,offset)[0];record=wire[offset:offset+size+4]
            mirror.accept(record);frames.append(list(record));offset+=size+4
        actual={e['channel']:e['data'] for e in mirror_events if e['channel'] in ('state','bus')}
        self.assertEqual(actual,expected)
        self.assertEqual(len(actual['bus']['native']['joints']),15)
        def exact_js(value):
            if isinstance(value,int) and not isinstance(value,bool) and abs(value)>2**53-1:return str(value)
            if isinstance(value,list):return [exact_js(v) for v in value]
            if isinstance(value,dict):return {k:exact_js(v) for k,v in value.items()}
            return value
        config={'mode':'service','control_enabled':True,'ids':IDS,'names':NAMES,'labels':LABELS,'version':VERSION,'baseline':BASELINE}
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);(base/'package.json').write_text('{"type":"module"}')
            for name in ('raw-telemetry.js','raw-kinematics.js','service-builds.js'):shutil.copyfile(ROOT/'console/static'/name,base/name)
            script="""import assert from 'node:assert/strict';
import {decodeRecord,mergeMetadata,TelemetryStore} from './raw-telemetry.js';
let text='';for await(const part of process.stdin)text+=part;const input=JSON.parse(text);
const [meta,dynamic]=input.frames.map(f=>decodeRecord(new Uint8Array(f)).data);
const actual=Object.fromEntries(Object.entries(dynamic).map(([k,v])=>[k,mergeMetadata(meta.channels[k]||{},v)]));
assert.deepEqual(actual,input.expected);assert.ok(Object.is(actual.state.imu.gyro[1],-0));
const store=new TelemetryStore(input.config);for(const f of input.frames)store.accept(new Uint8Array(f));
const snapshot=store.snapshot();assert.equal(snapshot.servos.length,15);assert.equal(snapshot.servos.filter(s=>s.status==='live').length,15);
assert.ok(snapshot.state.frames.camera);assert.equal(snapshot.state.skeleton.length,meta.model.skeleton.length);
assert.ok(snapshot.state.skeleton.every(s=>s.pos.every(Number.isFinite)&&s.quat.every(Number.isFinite)));
assert.equal(store.recording().frames[0].state.skeleton.length,meta.model.skeleton.length);
console.log('PASS production Rust bytes → Python/JS exact fields → 15 joints + browser FK + existing recording');
"""
            (base/'test.mjs').write_text(script)
            result=subprocess.run(['node',str(base/'test.mjs')],input=json.dumps({'config':config,'frames':frames,'expected':exact_js(expected)}),text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)

    def test_browser_adapter_matches_existing_python_store_for_motion_commissioning_and_stale_samples(self):
        cfg={'mode':'service','control_enabled':True,'ids':IDS,'names':NAMES,'labels':LABELS,'version':VERSION,'baseline':BASELINE}
        mapping={'calibration':{'joints':[{'id':sid,'name':name,'calibrated':True,'zero_raw':2048,'direction':1,'min_rad':-2,'max_rad':2} for sid,name in zip(IDS,NAMES)]}}
        state={'joints':[i*.01 for i in range(15)],'targets':[i*.015 for i in range(15)],'safety':{'gravity':[.03,-.05,-.998]},'diagnostics':{'schema':'microduck-observer/v1','currents_ma':[1]*15,'velocities':[.5]*15,'slow':{'age_ms':100,'temps_c':[40]*15},'imu':{'gyro':[.1,.2,.3],'quat':[1,0,0,0],'ready':True,'sequence':3,'age_ms':1}}}
        joints=[{'id':sid,'name':name,'position_raw':2048+i,'position_rad':i*.01,'velocity_rad_s':.1,'calibrated':True,'feedback_fresh':True,'temperature_c':40,'voltage_v':8.2} for i,(sid,name) in enumerate(zip(IDS,NAMES))]
        bus={'build':'1fa8438-feetech-ft6-control.27','mode':'motion','phase':'control','cycle':1,'fresh_sample':True,'read_recovery':'fresh','policy_enabled':True,'homed':True,'native':{'sample_age_ms':2,'torque_state_confirmed':True,'imu_mount_verified':True,'joints':joints}}
        health={'imu':{'ready':True,'consecutive_stale_blocks':0},'motors':{'max_c':40,'hottest':NAMES[0]}}
        first=[{'channel':k,'data':v} for k,v in {'state':state,'bus':bus,'calibration':mapping,'health':health,'system':{'cpu_temp_c':88},'capabilities':{'accepted':True},'tof':{'subscription':{'accepted':True}}}.items()]
        commissioning={'build':bus['build'],'mode':'commissioning','phase':'ready','updated_at_us':1000100,'last_sample':{'at_us':1000000,'servos':[dict(row,calibrated=True) for row in joints],'imu':{'gravity':[0,0,-1],'gyro_rad_s':[0,0,0],'quaternion_wxyz':[1,0,0,0],'valid':True}},'torque_state':'single_joint_enabled','motion':{'id':20,'target_raw':2200},'imu_mount_verified':True}
        steps=[{'now':10,'events':first},{'now':10.2,'events':[]},{'now':11.6,'events':[]},{'now':12,'events':[{'channel':'bus','data':commissioning}]},{'now':12.1,'events':[{'channel':'tof','data':{'seq':1,'rows':8,'cols':8,'status':[5]*64,'distance_mm':[100]*64}}]},{'now':12.3,'events':[{'channel':'state','error':'test disconnect'}]}]
        now=[10];store=Store('service',clock=lambda:now[0],control_enabled=True);expected=[]
        for step in steps:
            now[0]=step['now']
            with patch('telemetry.time.time',return_value=1700000000+step['now']):
                for event in step['events']:store.ingest(event)
                expected.append(store.peek())
        payload={'config':cfg,'steps':steps,'expected':expected,'records':[list(frame(1,{'schema':'r17.raw.v1','channels':{'bus':{'native':{'fixed':'kept'}}}})),list(frame(2,{'bus':{'cycle':2,'native':{'sample_age_ms':1}}})),list(frame(4,{'system':{'cpu_temp_c':88}}))],'integer':list(frame(2,{'state':{'t_ns':2**64-1}})), 'nonfinite':list(frame(2,{'state':{'joints':[float('nan')]*15},'bus':{'mode':'motion','cycle':2**64-1,'native':{'sample_age_ms':1}}}))}
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);(base/'package.json').write_text('{"type":"module"}')
            for name in ('raw-telemetry.js','raw-kinematics.js','service-builds.js'):
                shutil.copyfile(ROOT/'console/static'/name,base/name)
            shutil.copyfile(ROOT/'packaging/test_raw_telemetry.mjs',base/'test.mjs')
            result=subprocess.run(['node',str(base/'test.mjs')],input=json.dumps(payload),text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)

if __name__=='__main__':unittest.main()
