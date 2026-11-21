// One threshold table for every metric card: the same value must give the same
// verdict whether it is drawn on the battery, servo or CPU card.
import assert from 'node:assert/strict';
import {LIMITS,level,alarmClass,alarmLabel,limitText} from '../static/alarms.js';
import {batteryTone,batteryCaption} from '../static/battery.js';

// Battery: low is bad, and the numbers match the pack the robot actually runs.
assert.equal(level('battery',100),'none');
assert.equal(level('battery',35),'none');
assert.equal(level('battery',34.9),'warn');
assert.equal(level('battery',20),'warn');
assert.equal(level('battery',19.9),'critical');
assert.equal(level('battery',0),'critical');

// Temperatures rise the other way.
assert.equal(level('servo',25),'none');
assert.equal(level('servo',59.9),'none');
assert.equal(level('servo',60),'warn');
assert.equal(level('servo',70),'critical');
assert.equal(level('cpu',55),'none');
assert.equal(level('cpu',75),'warn');
assert.equal(level('cpu',85),'critical');

// Missing is not hot: an absent sample must never paint a card red.
for(const missing of [null,undefined,NaN,Infinity,'60',{}])assert.equal(level('servo',missing),'none',String(missing));
assert.equal(level('cpu',null),'none');
assert.equal(level('battery',null),'none');
assert.equal(level('unknown-kind',999),'none');

assert.equal(alarmClass('servo',25),'metric');
assert.equal(alarmClass('servo',65),'metric alarm-warn');
assert.equal(alarmClass('servo',88),'metric alarm-critical');
assert.equal(alarmClass('battery',19),'metric alarm-critical');

assert.equal(alarmLabel('battery',10),'告警');
assert.equal(alarmLabel('battery',30),'注意');
assert.equal(alarmLabel('battery',80),'');
assert.equal(alarmLabel('cpu',90),'告警');

// Every card states its own line, so a red number is explainable.
assert.match(limitText('battery'),/35 % 注意/);
assert.match(limitText('battery'),/20 % 告警/);
assert.match(limitText('servo'),/60 °C 注意/);
assert.match(limitText('cpu'),/85 °C 告警/);
assert.equal(limitText('nope'),'');

// The battery card's own wording follows the same thresholds.
assert.equal(batteryTone(100),'ok');
assert.equal(batteryTone(30),'low');
assert.equal(batteryTone(10),'critical');
assert.equal(batteryTone(null),'unknown');
assert.match(batteryCaption(10,6.8,6.79),/低于 20 %/);
assert.match(batteryCaption(30,7.4,null),/低于 35 %/);
assert.doesNotMatch(batteryCaption(90,8.2,8.1),/低于/,'a healthy pack says nothing about limits');
assert.match(batteryCaption(90,8.2,8.1),/最低 8.10 V/);
assert.equal(batteryCaption(null,8.2,8.1),'等待 robot.health · 不自行换算');

// Limits are the documented ones, not whatever the test happens to pass.
assert.deepEqual(LIMITS.battery,{warn:35,critical:20,unit:'%'});
assert.deepEqual(LIMITS.servo,{warn:60,critical:70,unit:'°C'});
assert.deepEqual(LIMITS.cpu,{warn:75,critical:85,unit:'°C'});

console.log('alarms: OK');
