// Battery card: the two numbers it shows, and the frame that records them.
// Thresholds themselves are covered by test_alarms.mjs; this file checks that the
// card renders both charge and voltage and never invents either.
import assert from 'node:assert/strict';
import {batteryTone,batteryCaption,BATTERY_FULL_V,BATTERY_EMPTY_V} from '../static/battery.js';
import {alarmClass} from '../static/alarms.js';
import {historyFrame} from '../static/history-frame.js';

assert.equal(batteryTone(100),'ok');
assert.equal(batteryTone(30),'low');
assert.equal(batteryTone(10),'critical');
for(const missing of [null,undefined,NaN,Infinity])assert.equal(batteryTone(missing),'unknown',String(missing));

// The card uses the shared alarm class, so battery red is servo red is CPU red.
assert.equal(alarmClass('battery',80),'metric');
assert.equal(alarmClass('battery',30),'metric alarm-warn');
assert.equal(alarmClass('battery',9),'metric alarm-critical');

// Captions carry the reason, not just the tone.
assert.equal(batteryCaption(null,6.85,6.8),'等待 robot.health · 不自行换算');
assert.match(batteryCaption(15.4,6.85,6.82),/6\.85 V/);
assert.match(batteryCaption(15.4,6.85,6.82),/低于 20 %/);
assert.match(batteryCaption(80,7.9,7.81),/最低 7\.81 V/);
assert.match(batteryCaption(80,7.9,null),/满 8\.2 \/ 空 6\.6/);
assert.match(batteryCaption(80,undefined,null),/满 8\.2 \/ 空 6\.6/);
assert.equal(BATTERY_FULL_V,8.2);
assert.equal(BATTERY_EMPTY_V,6.6);

// Recording frames carry both numbers, so a replay shows what was on screen.
const frame=historyFrame({at:1,mode:'service',channels:{health:{status:'live'}},
  health:{battery:{volts:8.15,percent:97.2}}});
assert.deepEqual(frame.health.battery,{volts:8.15,percent:97.2});
assert.equal(historyFrame({at:2,mode:'service',channels:{}}).health.battery.percent,undefined);

console.log('battery card: OK');
