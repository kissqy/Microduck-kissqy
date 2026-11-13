// Save the installed Walk model's action scale through the existing service job.
import {jointExecutionProfile,jointProfileSummary} from './execution-profile.js';

export class AdvancedParameters {
  constructor(owner){
    this.owner=owner;this.root=document.createElement('div');this.root.className='advanced-parameter-editor';
    this.root.innerHTML=`<div class="global-scale-row"><label id="management-scale-label" for="management-scale">联合模型动作缩放</label><input id="management-scale" aria-label="联合模型动作缩放" type="range" min="0.10" max="1.00" step="0.01" value="1.00" disabled><output id="management-scale-value">1.00（默认）</output><button class="button" id="management-scale-apply" disabled>应用联合缩放</button></div>
<span id="management-live-scale" class="tiny muted"></span>
<span id="management-scale-status" class="tiny muted" role="status"></span>
`;
    document.querySelector('#control-panel .runtime-parameters>p:last-child')?.before(this.root);
    this.$=id=>this.root.querySelector('#management-'+id);
    this.$('scale-apply').onclick=()=>this.applyScale();
    this.$('scale').oninput=()=>this.paint(this.snapshot,this.options);
  }
  async applyScale(){
    if(this.scaleBlocked)return;
    const scale=Number(this.$('scale').value);
    if(!Number.isFinite(scale)||scale<.1||scale>1)return;
    if(!confirm(`应用${this.jointScale?'联合模型':'动作'}缩放，释放扭矩并重启固件。请支撑机身，完成后重新 HOME。`))return;
    await this.owner.command({action:'set-action-scale',model:this.scaleModel.id,scale,supported:true});
  }
  paint(s={},options={}){
    this.snapshot=s;this.options=options;const job=s.service_control||{};
    this.scaleModel=this.owner.catalog?.models.find(row=>row.slot==='walk'&&row.active&&row.available);
    const bus=s.bus||{};
    const loadedWalk=bus.loaded_models?.walk;
    const matchingLoaded=!this.scaleModel||loadedWalk?.sha256===this.scaleModel.sha256?loadedWalk:null;
    // The editable value comes from the installed model's saved profile. The
    // running daemon can still report the previous profile until its restart.
    const boundProfile=jointExecutionProfile(this.scaleModel)??jointExecutionProfile(matchingLoaded);
    const displayProfile=jointExecutionProfile((bus.policy_enabled?bus.active_model:null)??bus.loaded_models?.walk??this.scaleModel);
    this.jointScale=!!boundProfile;
    this.profileLocked=this.jointScale&&!this.owner.catalog?.management_actions?.includes('joint-action-scale');
    this.globalScale=(s.service_sample_fresh?s.bus?.action_scale:null)??this.owner.catalog?.action_scale;
    const actualScale=this.jointScale?boundProfile.action_scale:this.globalScale;
    this.savedScale=actualScale;
    const scaleKnown=Number.isFinite(actualScale);
    const scaleKey=`${this.scaleModel?.id||''}:${this.jointScale?'joint':'global'}:${actualScale}`;
    if(scaleKnown&&(scaleKey!==this.scaleKey||this.profileLocked)){this.scaleKey=scaleKey;this.$('scale').value=String(Math.min(1,Math.max(.1,actualScale)));}
    this.$('scale-value').textContent=scaleKnown?Number(this.$('scale').value).toFixed(2):'—';
    const scaleLabel=this.jointScale?'联合模型动作缩放':'官方动作缩放';
    this.$('scale-label').textContent=scaleLabel;this.$('scale').setAttribute?.('aria-label',scaleLabel);
    this.$('scale-apply').textContent=this.jointScale?'应用联合缩放':'应用';
    const defaultLabel=document.getElementById('parameter-action-default'),defaultScale=this.owner.catalog?.default_action_scale;
    const jointDefault=this.owner.catalog?.default_joint_action_scale??1;
    if(defaultLabel)defaultLabel.textContent=displayProfile?`联合模型 · 默认 ${jointDefault.toFixed(2)}`:`${Number.isFinite(defaultScale)?'默认 '+defaultScale.toFixed(2):'等待默认值'} · 行走 / 保持`;
    const scaleSupported=this.owner.catalog?.management_actions?.includes(this.jointScale?'joint-action-scale':'action-scale')&&!!this.scaleModel;
    this.scaleBlocked=!!(this.owner.recoveryBlocked||this.owner.loading||this.owner.panel.posting||job.busy||job.stopping||options.replay||options.offline||!scaleSupported||!scaleKnown||this.profileLocked);
    this.$('scale').disabled=this.scaleBlocked;
    const edited=Number(this.$('scale').value),valid=Number.isFinite(edited)&&edited>=.1&&edited<=1;
    this.$('scale-apply').disabled=!!(this.scaleBlocked||!valid||edited===actualScale);
    const scaleReason=options.replay||options.offline?'回放 / 离线时不可应用':job.busy||job.stopping||this.owner.panel.posting?'服务操作中，请稍候':this.owner.catalogError?`配置读取失败：${this.owner.catalogError}；将自动重读`:this.owner.loading||!this.owner.catalog?'正在读取 Zero 配置':!this.scaleModel?'没有已启用且可用的行走模型':!scaleSupported?'Zero 服务未提供动作缩放设置，请升级本版配套服务':!scaleKnown?'等待已保存的动作缩放':!valid?'动作缩放须为 0.10–1.00':this.jointScale?`联合缩放默认 ${jointDefault.toFixed(2)}，已保存 ${actualScale.toFixed(2)}；作用于联合模型的保持、行走与起身。编辑暂不生效；应用后保存，重启后保留。`:'编辑暂不生效；应用后保存动作缩放，重启后保留。';
    this.$('scale-status').textContent=scaleReason;
    this.$('scale').title=this.$('scale-apply').title=scaleReason;
    const applied=s.bus?.active_action_scale;
    const filters=bus.policy_enabled?bus.active_target_filters:bus;
    const live=displayProfile?bus.policy_enabled?`联合模型 · 统一输出参数 · 基础 ${displayProfile.action_scale.toFixed(2)} · 头 ${filters?.head_lowpass??'—'} / 腿 ${filters?.legs_lowpass??'—'}${Number.isFinite(applied)?' · 实际 '+applied.toFixed(3):' · 实际倍率待回读'}`:`联合模型统一配置：${jointProfileSummary(displayProfile)} · 策略未启用`:`官方行走 ${bus.action_scale??'—'} · 起坐基础 1 · 头 ${filters?.head_lowpass??'—'} / 腿 ${filters?.legs_lowpass??'—'}${Number.isFinite(applied)?' · 当前 '+applied.toFixed(3):''}`;
    this.$('live-scale').textContent=!s.service_sample_fresh?'等待运行反馈':live;
  }
}
