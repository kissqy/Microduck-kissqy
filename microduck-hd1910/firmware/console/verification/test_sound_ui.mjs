// Voice panel rules: which refusal becomes which sentence, and when a button may
// be pressed at all. Pure functions, no DOM and no audio.
import assert from 'node:assert/strict';
import {refusalText,refusalHint,playableState} from '../static/sound-test.js';

// Commissioning mode is the refusal this board produces today; the message has
// to point at the thing a person can do about it.
assert.match(refusalText('robotd is read-only: motor commands are disabled; uncalibrated telemetry is available via robot.busStatus'),/标定模式/);
assert.doesNotMatch(refusalText('robotd is read-only: motor commands are disabled'),/motor commands/,
  'the raw daemon sentence is replaced by an actionable one');
// The pointer to the mode switch is separate, so it is never printed twice.
assert.equal(refusalHint('当前 robotd 处于标定模式，官方接口拒绝发声'),'到「机器人服务模式」切到运动模式后再试');
assert.equal(refusalHint('a robotd is read-only'),'到「机器人服务模式」切到运动模式后再试');
assert.equal(refusalHint('音库没有渲染出 wav'),'');
assert.equal(refusalHint(''),'');
assert.doesNotMatch(refusalText('robotd is read-only'),/运动模式/,'the cause sentence carries no instruction');
assert.match(refusalText('audio is not enabled in /etc/robot/feetech-ft5/robotd.toml'),/enabled = false/);
assert.match(refusalText('the voice bank at /var/lib/robot/sounds has no wav'),/音库/);
assert.match(refusalText('', {message:'voice bank empty'}),/音库/);
// Anything unrecognised survives verbatim: guessing would hide the real reason.
assert.equal(refusalText('PCM busy'),'PCM busy');
assert.equal(refusalText(''),'robotd 没有说明拒绝原因');
assert.equal(refusalText(undefined,null),'robotd 没有说明拒绝原因');

assert.deepEqual(playableState({online:true,replay:false,busy:false,catalog:{can_play:true}}),
  {disabled:false,reason:''});
assert.equal(playableState({online:false}).reason,'尚未连接 Zero');
assert.equal(playableState({online:true,replay:true}).disabled,true);
assert.equal(playableState({online:true,busy:true}).reason,'正在提交上一次播放');
assert.equal(playableState({online:true,catalog:{can_play:false,reason:'音库空'}}).reason,'音库空');
// Without --feetech there is no service transport, so a click would 503.
assert.equal(playableState({online:true,serviceEnabled:false}).reason,'声音测试需要 --feetech 服务模式');
// A stale "cannot play" verdict from before a repair must not lock the panel.
assert.equal(playableState({online:true,catalog:null}).disabled,false);

console.log('sound panel: OK');
