// Service rows: state labels, hardware chips, and when the autostart button may
// be shown. Pure functions only — the panel's DOM half is exercised by the page.
import assert from 'node:assert/strict';
import {unitState,autostartState,hardwareChip,servoChip,tofChip,memoryText,autostartCommand,autostartLabel,autostartReason,manualActionCommand,manualActionReason,robotdStopReason,summary} from '../static/processes.js';

const META={unit:'mediad.service',label:'摄像头服务',hardware:['camera'],autostart:true,manual_actions:['start','stop']};
const READONLY={unit:'robotd.service',label:'运动控制守护',hardware:['servo_bus','servos'],autostart:false,manual_actions:['start','stop']};
const HW={camera:{label:'IMX219 摄像头',detail:'V4L2 采集节点'}};

// Run state: a failed unit is not merely "not active", and a unit that was never
// installed is not reported as stopped-and-fine.
assert.deepEqual(unitState({active:'active',sub:'running',load:'loaded'}),{tone:'live',label:'运行'});
assert.deepEqual(unitState({active:'failed',sub:'failed',load:'loaded'}),{tone:'bad',label:'失败'});
assert.deepEqual(unitState({active:'inactive',sub:'dead',load:'masked'}),{tone:'neutral',label:'停止'});
assert.deepEqual(unitState({active:'inactive',sub:'dead',load:'not-found'}),{tone:'neutral',label:'未安装'});
assert.deepEqual(unitState({active:'activating',sub:'start',load:'loaded'}),{tone:'warn',label:'启动中'});
assert.deepEqual(unitState({active:'active',sub:'exited',load:'loaded'}),{tone:'live',label:'运行 · 已退出'});

// Boot behaviour keeps `masked` distinct from `disabled`: they are different
// states, and only one of them needs an unmask before it can be enabled.
assert.deepEqual(autostartState({enabled:'enabled',load:'loaded'}),{tone:'live',label:'开机自启'});
assert.deepEqual(autostartState({enabled:'disabled',load:'loaded'}),{tone:'neutral',label:'不自启'});
assert.deepEqual(autostartState({enabled:'masked',load:'masked'}),{tone:'warn',label:'已屏蔽'});
assert.deepEqual(autostartState({enabled:'static',load:'loaded'}),{tone:'neutral',label:'内建'});
assert.deepEqual(autostartState({enabled:'',load:'not-found'}),{tone:'neutral',label:'—'});
// This board's tofd: a mask with no unit file behind it.
assert.deepEqual(autostartState({enabled:'masked',load:'masked',installed:false}),{tone:'warn',label:'已屏蔽 · 未安装'});

// Hardware is three-state: an unasked ToF is neither present nor absent.
assert.deepEqual(hardwareChip('camera',{present:true,detail:'imx219'},HW.camera),
  {tone:'live',symbol:'●',label:'IMX219 摄像头',detail:'imx219'});
assert.deepEqual(hardwareChip('camera',{present:false,detail:'无 /dev/video0'},HW.camera),
  {tone:'bad',symbol:'○',label:'IMX219 摄像头',detail:'无 /dev/video0'});
assert.deepEqual(hardwareChip('tof',{present:null,detail:'待探测'},{label:'VL53L5CX 测距'}),
  {tone:'neutral',symbol:'◌',label:'VL53L5CX 测距',detail:'待探测'});
assert.equal(hardwareChip('tof',{present:false},{}).tone,'bad');
assert.equal(hardwareChip('tof',{},{}).label,'tof','an unknown id still renders its own name');

// The servos are only visible through robotd: full feedback is present, no
// feedback while the service runs is the failure worth colouring red.
assert.deepEqual(servoChip(15),{tone:'live',symbol:'●',label:'HD-1910 舵机',detail:'15/15 有反馈'});
assert.deepEqual(servoChip(11),{tone:'warn',symbol:'◐',label:'HD-1910 舵机',detail:'11/15 有反馈'});
assert.deepEqual(servoChip(0),{tone:'bad',symbol:'○',label:'HD-1910 舵机',detail:'没有关节反馈'});
assert.deepEqual(servoChip(null),{tone:'neutral',symbol:'◌',label:'HD-1910 舵机',detail:'等待 robotd 反馈'});

// Frames arriving are stronger evidence than a probe that has not run.
assert.equal(tofChip({present:null,detail:'待探测'},true).detail,'正在出帧');
assert.equal(tofChip({present:null,detail:'待探测'},false).symbol,'◌');

assert.equal(memoryText(48230400),'46 MiB');
assert.equal(memoryText(2*1024**3),'2.0 GiB');
assert.equal(memoryText(0),'—');
assert.equal(memoryText(null),'—');
assert.equal(memoryText(1),'1 MiB','a tiny resident process still shows something');

// Autostart commands: robotd is read-only, not-found and static are unavailable,
// and a masked unit offers enable (which unmasks first) but never a bare disable.
assert.equal(autostartCommand({load:'loaded',enabled:'disabled'},META,true).enabled,true);
assert.equal(autostartCommand({load:'loaded',enabled:'enabled'},META,false).enabled,false);
assert.equal(autostartCommand({load:'loaded',enabled:'disabled'},READONLY,true),null);
assert.equal(autostartCommand({load:'not-found',enabled:''},META,true),null);
assert.equal(autostartCommand({load:'loaded',enabled:'static'},META,true),null);
assert.equal(autostartCommand({load:'masked',enabled:'masked'},META,false),null);
assert.equal(autostartCommand({load:'masked',enabled:'masked'},META,true).enabled,true);
// Nothing to enable when the mask has no unit behind it.
assert.equal(autostartCommand({load:'masked',enabled:'masked',installed:false},META,true),null);
assert.equal(autostartLabel({load:'masked',enabled:'masked',installed:false},META),'未安装');
assert.match(autostartReason({load:'masked',enabled:'masked',installed:false},META),/没有安装/);

assert.equal(autostartLabel({enabled:'masked'},META),'开启开机自启（会先解除屏蔽）');
assert.equal(autostartLabel({enabled:'disabled'},META),'设为开机自启');
assert.equal(autostartLabel({enabled:'enabled'},META),'取消开机自启');
assert.equal(autostartLabel({},READONLY),'只读');
assert.equal(autostartReason({},READONLY),'该服务只能查看，不能从中控修改开机自启');
assert.equal(autostartReason({load:'not-found'},META),'本机未安装 mediad.service');
assert.equal(autostartReason({load:'loaded',enabled:'static'},META),'内建 unit，不能改自启');
assert.equal(autostartReason({load:'loaded',enabled:'enabled'},META),'');

// Manual service actions are a separate allowlist from boot policy. robotd can
// start normally, but stop requires fresh evidence that all torque is already off.
const commissioning={service_sample_fresh:true,bus:{mode:'commissioning',phase:'ready',torque_state:'off'}};
assert.deepEqual(manualActionCommand({load:'loaded',installed:true,active:'inactive'},META,'start',commissioning),
  {action:'unit-control',unit:'mediad.service',operation:'start',supported:true});
assert.deepEqual(manualActionCommand({load:'loaded',installed:true,active:'active'},META,'stop',commissioning),
  {action:'unit-control',unit:'mediad.service',operation:'stop',supported:true});
assert.equal(manualActionCommand({load:'masked',enabled:'masked',active:'inactive'},META,'start',commissioning),null);
assert.equal(manualActionCommand({load:'not-found',installed:false,active:'inactive'},META,'start',commissioning),null);
assert.equal(manualActionCommand({load:'loaded',active:'active'},META,'stop',commissioning,true),null);
assert.equal(manualActionCommand({load:'loaded',active:'active'},READONLY,'stop',
  {service_sample_fresh:true,bus:{mode:'commissioning',phase:'ready',torque_state:'single_joint_enabled'}}),null);
assert.match(robotdStopReason({service_sample_fresh:false,bus:{}}),/新鲜反馈/);
assert.deepEqual(manualActionCommand({load:'loaded',active:'inactive'},READONLY,'start',{}),
  {action:'unit-control',unit:'robotd.service',operation:'start',supported:true});
assert.equal(manualActionCommand({load:'loaded',active:'inactive'},
  {unit:'aic3104-init.service',manual_actions:['start']},'stop',commissioning),null);
const safeMotion={service_sample_fresh:true,bus:{mode:'motion',phase:'control',fresh_sample:true,
  policy_enabled:false,torque_off_pending:false,native:{torque_state_confirmed:false,
    hd1910:{restore_pending:false,temporary_gains_applied:false}}}};
assert.equal(robotdStopReason(safeMotion),'');
assert.notEqual(robotdStopReason({...safeMotion,bus:{...safeMotion.bus,policy_enabled:true}}),'');

assert.equal(summary([{active:'active',enabled:'enabled',load:'loaded'},
                      {active:'inactive',enabled:'masked',load:'masked'},
                      {active:'failed',enabled:'disabled',load:'loaded'},
                      {active:'inactive',enabled:'',load:'not-found'}]),
  '1/4 运行 · 1 失败 · 1 已屏蔽 · 1 未安装');
assert.equal(summary([]),'');

console.log('process panel: OK');
