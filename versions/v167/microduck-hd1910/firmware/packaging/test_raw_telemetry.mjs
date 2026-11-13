import assert from 'node:assert/strict';
import {TelemetryStore,decodeRecord,mergeMetadata} from './raw-telemetry.js';
let input='';for await(const part of process.stdin)input+=part;const data=JSON.parse(input);
let now=10;const store=new TelemetryStore(data.config,()=>now,()=>1700000000+now);store.auxiliary({connection_paused:false});
function equivalent(actual,expected,path='snapshot'){
  if(typeof expected==='number'){assert.equal(typeof actual,'number',path);assert.ok(Math.abs(actual-expected)<=Math.max(1e-9,Math.abs(expected)*1e-12),`${path}: ${actual} != ${expected}`);return;}
  if(expected===null||typeof expected!=='object'){assert.equal(actual,expected,path);return;}
  assert.equal(Array.isArray(actual),Array.isArray(expected),path);assert.deepEqual(Object.keys(actual).sort(),Object.keys(expected).sort(),path);
  for(const key of Object.keys(expected))equivalent(actual[key],expected[key],path+'.'+key);
}
for(let i=0;i<data.steps.length;i++){
  const step=data.steps[i];now=step.now;for(const event of step.events)store.ingest(event);
  const snap=store.snapshot(false);for(const key of ['control','service_control','connection'])delete snap[key];equivalent(snap,data.expected[i]);
}
const streamed=new TelemetryStore(data.config,()=>now,()=>1700000000+now);for(const frame of data.records)streamed.accept(new Uint8Array(frame));
assert.equal(streamed.data.bus.native.fixed,'kept');assert.equal(streamed.data.bus.cycle,2);assert.equal(streamed.data.system.cpu_temp_c,88);
assert.equal(decodeRecord(new Uint8Array(data.integer)).data.state.t_ns,'18446744073709551615');
streamed.kinematics={};streamed.accept(new Uint8Array(data.nonfinite));
assert.equal(streamed.data.state.joints[0],null);assert.equal(streamed.data.state.frames,null);assert.deepEqual(streamed.data.state.skeleton,[]);
assert.equal(streamed.snapshot().servos[0].angle_deg,null,'Missing measurement must not become a zero angle');
assert.equal(streamed.history.length,1,'Exact decimal u64 cycle still identifies an active motion recording');
const previousSample=streamed.busSampleAt;now+=.02;streamed.ingest({channel:'bus',data:{mode:'motion',cycle:'18446744073709551614'}});assert.ok(streamed.busSampleAt>previousSample,'Large exact counters still advance freshness');
const poison=JSON.parse('{"__proto__":{"bad":true},"constructor":3}');assert.equal(mergeMetadata({},poison).__proto__.bad,true);assert.equal({}.bad,undefined);
// The recording stays the existing replay format and bounded at 1200 frames.
streamed.auxiliary({inspection_active:true,service_commands:[{action:'capture'}]});
for(let i=0;i<1250;i++){now+=.1;streamed.snapshot();}
const recording=streamed.recording();assert.equal(recording.schema,'microduck-console-recording/v1');assert.equal(recording.frames.length,1200);assert.deepEqual(recording.service_commands,[{action:'capture'}]);
assert.ok(recording.frames.every(f=>f.schema==='microduck-console/v1'&&f.servos.length===15&&f.state&&f.health&&f.system&&f.imu&&f.tof));
streamed.disconnect();assert.equal(streamed.recording().frames.length,1200,'Disconnect keeps the completed recording available for export');assert.equal(streamed.channels.bus.status,'error');
streamed.reset();assert.equal(streamed.history.length,0,'A new target starts a distinct recording');
assert.ok(!Object.hasOwn(recording.frames[0],'events'));assert.ok(!Object.hasOwn(recording.frames[0].bus,'last_failure'));
console.log('PASS browser adapter parity, wire precision, metadata merging and bounded legacy recording');
