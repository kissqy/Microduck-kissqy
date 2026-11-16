// Battery card rules: thresholds, tone class, caption, and the recording frame.
// Runs without a browser or a robot: the module under test is pure.
import assert from 'node:assert/strict';
import {batteryTone,batteryClass,batteryCaption,BATTERY_FULL_V,BATTERY_EMPTY_V} from '../static/battery.js';
import {historyFrame} from '../static/history-frame.js';

// Thresholds are what the caption claims: <20 critical, 20-35 low, >=35 ok.
assert.equal(batteryTone(100),'ok');
assert.equal(batteryTone(35),'ok');
assert.equal(batteryTone(34.9),'low');
assert.equal(batteryTone(20),'low');
assert.equal(batteryTone(19.9),'critical');
assert.equal(batteryTone(0),'critical');

// Missing is never zero: an absent reading is unknown, not a flat pack.
for(const missing of [null,undefined,NaN,Infinity,-Infinity])assert.equal(batteryTone(missing),'unknown',String(missing));

assert.equal(batteryClass(80),'metric');
assert.equal(batteryClass(null),'metric');
assert.equal(batteryClass(30),'metric battery-low');
assert.equal(batteryClass(9),'metric battery-critical');

// A stale health channel must not produce a number from a voltage.
assert.equal(batteryCaption(null,6.85,6.8),'等待 robot.health · 不自行换算');

// The reading the board reported before it went offline (6.847 V / 15.4 %).
assert.equal(batteryCaption(15.4,6.85,6.82),'6.85 V · 电量低，行走会欠压掉电');

assert.equal(batteryCaption(80,7.9,7.81),'7.90 V · 最低 7.81 V');
assert.equal(batteryCaption(80,7.9,null),'7.90 V · 满 8.2 / 空 6.6');
assert.equal(batteryCaption(30,7.4,null),'7.40 V · 偏低，大动作前先充电');
assert.equal(batteryCaption(80,undefined,7.81),'最低 7.81 V');
assert.equal(batteryCaption(80,undefined,undefined),'满 8.2 / 空 6.6');
assert.equal(BATTERY_FULL_V,8.2);
assert.equal(BATTERY_EMPTY_V,6.6);

// Recording frames carry the percentage, so replay shows what was on screen.
const frame=historyFrame({at:1,mode:'service',channels:{health:{status:'live'}},health:{battery:{volts:6.85,percent:15.4}}});
assert.deepEqual(frame.health.battery,{volts:6.85,percent:15.4});

// A frame without a health sample keeps the field absent rather than inventing 0 %.
assert.equal(historyFrame({at:2,mode:'service',channels:{}}).health.battery.percent,undefined);

console.log('battery card: OK');
