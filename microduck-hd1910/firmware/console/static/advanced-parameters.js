// Temporary P/D/torque test UI; the main console retains its original model flow.
import {jointExecutionProfile,jointProfileSummary} from './execution-profile.js';

export class AdvancedParameters {
  constructor(owner){
    this.owner=owner;this.root=document.createElement('div');this.root.className='advanced-parameter-editor';
    this.root.innerHTML=`      <div class="servo-parameter-row"><label>P（50号）· 比例增益<input id="management-kp" aria-label="位置环比例增益 / Position Proportional Gain" title="位置环比例增益 / Position Proportional Gain" type="number" min="0" max="255" step="1" disabled><small id="management-kp-saved">等待读取</small></label><label>D（51号）· 微分增益<input id="management-kd" aria-label="位置环微分增益 / Position Derivative Gain" title="位置环微分增益 / Position Derivative Gain" type="number" min="0" max="255" step="1" disabled><small id="management-kd-saved">等待读取</small></label><label>48号 · 转矩限制<input id="management-torque-limit" aria-label="转矩限制 / Torque Limit" title="转矩限制 / Torque Limit" type="number" min="0" max="1000" step="1" disabled><small id="management-torque-limit-saved">等待读取</small></label></div>
      <div class="global-scale-row"><label id="management-scale-label" for="management-scale">官方动作缩放</label><input id="management-scale" aria-label="官方动作缩放" type="range" min="0.10" max="1.00" step="0.01" disabled><output id="management-scale-value">—</output><button class="button" id="management-scale-apply" disabled>应用</button></div>
<span id="management-live-scale" class="tiny muted"></span>
<span id="management-scale-status" class="tiny muted" role="status"></span>
`;
    document.querySelector('#control-panel .runtime-parameters>p:last-child')?.before(this.root);
    this.$=id=>this.root.querySelector('#management-'+id);
    this.$('scale-apply').onclick=()=>this.applyScale();
    for(const name of ['kp','kd','torque-limit','scale'])this.$(name).oninput=()=>this.paint(this.snapshot,this.options);
  }
  async applyScale(){
    if(this.scaleBlocked)return;
    const servo=this.editedServo();
    if(!servo)return;
    if(!confirm(this.profileLocked?'应用 P、D、转矩限制，释放扭矩并重启固件；联合模型统一输出参数保持。请支撑机身，完成后重新 HOME。':'同时应用 P、D、转矩限制和动作缩放，释放扭矩并重启固件。请支撑机身，完成后重新 HOME。'))return;
    await this.owner.command({action:'set-action-scale',model:this.scaleModel.id,scale:this.profileLocked?this.savedScale:Number(this.$('scale').value),...servo,supported:true});
  }
  editedServo(){
    const values={kp:Number(this.$('kp').value),kd:Number(this.$('kd').value),torque_limit:Number(this.$('torque-limit').value)};
    return [['kp',255],['kd',255],['torque_limit',1000]].every(([name,max])=>Number.isInteger(values[name])&&values[name]>=0&&values[name]<=max)&&['kp','kd','torque-limit'].every(name=>this.$(name).value!=='')?values:null;
  }
  paint(s={},options={}){
    this.snapshot=s;this.options=options;const job=s.service_control||{};
    this.scaleModel=this.owner.catalog?.models.find(row=>row.slot==='walk'&&row.active&&row.available);
    const bus=s.bus||{};
    const boundProfile=jointExecutionProfile(Object.hasOwn(bus.loaded_models||{},'walk')?bus.loaded_models.walk:this.scaleModel);
    const displayProfile=jointExecutionProfile((bus.policy_enabled?bus.active_model:null)??bus.loaded_models?.walk??this.scaleModel);
    this.profileLocked=!!boundProfile;
    const actualScale=(s.service_sample_fresh?s.bus?.action_scale:null)??this.owner.catalog?.action_scale;
    this.savedScale=actualScale;
    const scaleKnown=Number.isFinite(actualScale);
    const scaleKey=`${actualScale}`;
    if(scaleKnown&&(scaleKey!==this.scaleKey||this.profileLocked)){this.scaleKey=scaleKey;this.$('scale').value=String(actualScale);}
    this.$('scale-value').textContent=scaleKnown?Number(this.$('scale').value).toFixed(2):'—';
    this.$('scale-label').textContent=this.profileLocked?'其他模型动作缩放（已保存）':'官方动作缩放';
    this.$('scale-apply').textContent=this.profileLocked?'应用舵机参数':'应用';
    const defaultLabel=document.getElementById('parameter-action-default'),defaultScale=this.owner.catalog?.default_action_scale;
    if(defaultLabel)defaultLabel.textContent=displayProfile?'联合模型 · 统一输出参数':`${Number.isFinite(defaultScale)?'默认 '+defaultScale.toFixed(2):'等待默认值'} · 行走 / 保持`;
    const appliedServo=this.owner.catalog?.servo_parameters,defaults=this.owner.catalog?.default_servo_parameters,saved=appliedServo??defaults;
    const servoKnown=saved&&['kp','kd','torque_limit'].every(k=>Number.isInteger(saved[k]));
    const servoKey=JSON.stringify(saved);
    if(servoKnown&&servoKey!==this.servoKey){this.servoKey=servoKey;this.$('kp').value=String(saved.kp);this.$('kd').value=String(saved.kd);this.$('torque-limit').value=String(saved.torque_limit);}
    for(const [id,key] of [['kp','kp'],['kd','kd'],['torque-limit','torque_limit']]){
      this.$(id+'-saved').textContent=servoKnown?appliedServo?`已保存 ${saved[key]}`:`默认 ${defaults?.[key]??'—'} · 待应用`:this.owner.catalogError?'读取失败':this.owner.catalog&&!this.owner.loading?'服务未提供参数':'等待读取';
    }
    const scaleSupported=this.owner.catalog?.management_actions?.includes('advanced-parameters')&&!!this.scaleModel&&servoKnown;
    this.scaleBlocked=!!(this.owner.recoveryBlocked||this.owner.loading||!scaleSupported||!scaleKnown);
    this.$('scale').disabled=this.scaleBlocked||this.profileLocked;
    const edited=this.editedServo();
    for(const id of ['kp','kd','torque-limit'])this.$(id).disabled=this.scaleBlocked;
    this.$('scale-apply').disabled=!!(this.scaleBlocked||!edited||(appliedServo&&Number(this.$('scale').value)===actualScale&&JSON.stringify(edited)===JSON.stringify(saved)));
    const scaleReason=options.replay||options.paused||options.offline?'回放 / 暂停 / 离线时不可应用':job.busy||job.stopping||this.owner.panel.posting||this.owner.uploading?'服务操作中，请稍候':this.owner.catalogError?`配置读取失败：${this.owner.catalogError}；将自动重读`:this.owner.loading||!this.owner.catalog?'正在读取 Zero 配置':!this.owner.catalog.management_actions?.includes('advanced-parameters')?'Zero 服务配置未提供高级参数；请核对系统日志中的安装结果':!this.scaleModel?'没有已启用且可用的行走模型':!servoKnown?'Zero 未返回 P / D / 转矩限制配置':!edited?'P / D 须为 0–255 整数，转矩限制须为 0–1000 整数':this.profileLocked?`联合模型使用统一输出参数（${jointProfileSummary(boundProfile)}）；此处全局保存值仅供其他模型。应用仍可保存 P / D / 转矩限制，重启保留。`:'编辑暂不生效；应用同时保存 P / D / 转矩限制及缩放，重启保留。全部 15 个舵机共用。';
    this.$('scale-status').textContent=scaleReason;
    this.$('scale').title=this.$('scale-apply').title=scaleReason;
    const applied=s.bus?.active_action_scale;
    const native=s.bus?.native?.hd1910,actualServo=native?.servo_parameters;
    const servoReadback=native?.temporary_gains_applied&&actualServo?` · 舵机已确认 P ${actualServo.kp} / D ${actualServo.kd} / 转矩 ${actualServo.torque_limit}`:' · 舵机参数待 HOME 上力确认';
    const filters=bus.policy_enabled?bus.active_target_filters:bus;
    const live=displayProfile?bus.policy_enabled?`联合模型 · 统一输出参数 · 基础 ${displayProfile.action_scale.toFixed(2)} · 头 ${filters?.head_lowpass??'—'} / 腿 ${filters?.legs_lowpass??'—'}${Number.isFinite(applied)?' · 实际 '+applied.toFixed(3):' · 实际倍率待回读'}`:`联合模型统一配置：${jointProfileSummary(displayProfile)} · 策略未启用`:`官方行走 ${bus.action_scale??'—'} · 起坐基础 1 · 独立起身 ${bus.model_action_scales?.stand_test??bus.model_action_scales?.stand??'—'} · 头 ${filters?.head_lowpass??'—'} / 腿 ${filters?.legs_lowpass??'—'}${Number.isFinite(applied)?' · 当前 '+applied.toFixed(3):''}`;
    this.$('live-scale').textContent=!s.service_sample_fresh?'等待运行反馈':live+servoReadback;
  }
}
