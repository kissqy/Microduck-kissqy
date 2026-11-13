import assert from 'node:assert/strict';
import fs from 'node:fs';
import {deriveKinematics} from '../console/static/raw-kinematics.js';

const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
let compared=0,maxError=0;
function compare(actual,expected,path='root') {
  if(typeof expected==='number') {
    assert.equal(typeof actual,'number',path);
    const error=Math.abs(actual-expected);maxError=Math.max(maxError,error);compared++;
    assert.ok(error<=1e-10,`${path}: ${actual} != ${expected}, error ${error}`);return;
  }
  if(expected!==null&&typeof expected==='object') {
    assert.deepEqual(Object.keys(actual).sort(),Object.keys(expected).sort(),path+' fields');
    for(const key of Object.keys(expected))compare(actual[key],expected[key],path+'.'+key);
  }else assert.equal(actual,expected,path);
}
for(const [index,sample] of fixture.cases.entries()) {
  const before=JSON.stringify([fixture.definition,sample]);
  compare(deriveKinematics(fixture.definition,sample.wire_names,sample.positions),sample.expected,'case'+index);
  assert.equal(JSON.stringify([fixture.definition,sample]),before,'FK must not mutate metadata or raw data');
}
const sample=fixture.cases[1];
assert.throws(()=>deriveKinematics({...fixture.definition,schema:'unsupported'},sample.wire_names,sample.positions));
const badTree=structuredClone(fixture.definition);badTree.bodies[1].parent=1;
assert.throws(()=>deriveKinematics(badTree,sample.wire_names,sample.positions));
assert.throws(()=>deriveKinematics(fixture.definition,sample.wire_names,[NaN]));
const noImu=structuredClone(fixture.definition);delete noImu.sites.head_imu;
assert.equal(Object.hasOwn(deriveKinematics(noImu,sample.wire_names,sample.positions).frames,'head_imu'),false);
console.log(JSON.stringify({native_pose_cases:fixture.cases.length,numeric_values_compared:compared,max_absolute_error:maxError,invalid_metadata_rejected:true,inputs_immutable:true}));
