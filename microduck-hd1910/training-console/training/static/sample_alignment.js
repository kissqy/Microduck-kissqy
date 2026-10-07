'use strict';
// The backend applies the same boundary rules to the real config. This local
// preview never probes the training computer or edits cached official configs.
const sampleAlignment = {
  referenceEnvs:4096, referenceSteps:24,
  strictFunctions:new Set(['reward_weight','standing_envs_curriculum','velocity_tracking_std_curriculum',
    'push_curriculum','wheel_friction_curriculum','com_range_curriculum',
    'velocity_command_ranges_curriculum','face_down_prob_curriculum']),
  strict(term){return this.strictFunctions.has((term?.func?.callable||'').split('.').at(-1));},
  budget(rounds,envs,steps=24){return Math.ceil(rounds*4096*24/(envs*steps));},
  threshold(step,envs,strict){const value=step*4096/envs;return strict?Math.floor(value):Math.ceil(value);},
  preview(full,envs){
    if(!full?.env||!Number.isInteger(envs)||envs<1||envs>8192)return {full,alignment:null};
    const out=structuredClone(full),stages=[];
    for(const [name,term] of Object.entries(out.env.curriculum||{})){
      if(!term)continue;
      const strict=this.strict(term);
      for(const [key,values] of Object.entries(term.params||{})){
        if(!key.endsWith('_stages')||!Array.isArray(values))continue;
        values.forEach((s,index)=>{
          if(!Number.isInteger(s?.step)||s.step<0)return;
          const original=s.step;s.step=this.threshold(original,envs,strict);
          stages.push({term:name,key,index,reference_step:original,step:s.step,strict});
        });
      }
    }
    return {full:out,alignment:{version:1,reference_envs:4096,reference_steps_per_iteration:24,
      num_envs:envs,steps_per_iteration:out.agent.num_steps_per_env,
      factor:4096/envs,iteration_factor:4096*24/(envs*out.agent.num_steps_per_env),stages}};
  }
};
