const finite=value=>typeof value==='number'&&Number.isFinite(value);
const fmt=value=>finite(value)?value.toFixed(2):'—';

// Catalog/loaded metadata describes the model's fixed output mapping. Current
// scale and filter readback still come from the daemon's existing live fields.
export function jointExecutionProfile(model){
  const profile=model?.runtime_execution_profile??model?.execution_profile;
  return profile?.schema==='microduck-runtime-execution/v1'
    &&profile.mode==='uniform'
    &&typeof model?.sha256==='string'&&profile.model_sha256===model.sha256
    &&finite(profile.action_scale)&&profile.action_scale>=.1&&profile.action_scale<=2
    &&['head_lowpass','legs_lowpass'].every(key=>finite(profile[key])&&profile[key]>0&&profile[key]<=1)
    ?profile:null;
}

export function jointProfileSummary(profile){
  return `基础 ${fmt(profile?.action_scale)} / 头 ${fmt(profile?.head_lowpass)} / 腿 ${fmt(profile?.legs_lowpass)}`;
}

export const jointExecutionNotice='联合模型全程使用统一输出参数，电压补偿沿用配置。';
