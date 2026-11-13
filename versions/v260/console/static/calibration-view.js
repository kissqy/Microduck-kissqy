import {REFERENCE_IDS,REFERENCE_LABELS,hasReferenceHinge} from './calibration-reference.js';
import {officialStandingDegrees,referenceAngle} from './joint-reference.js';

const set=(id,value)=>{const el=document.getElementById(id);if(el&&el.textContent!==value)el.textContent=value;};
export class CalibrationViewPanel{
  constructor(view){
    this.view=view;
    for(const mode of ['measured','zero','home','positive','negative']){
      document.getElementById(`pose-reference-${mode}`).onclick=()=>view.setReference(mode);
    }
    view.onDisplayChange=()=>this.paint();this.paint();
  }
  paint(){
    const view=this.view,sample=view.lastSample,index=view.selected??0,id=REFERENCE_IDS[index],label=REFERENCE_LABELS[index];
    const mode=view.referenceMode,reference=mode!=='measured',hinge=hasReferenceHinge(index);
    document.querySelector('.twin-panel').dataset.reference=String(reference);
    for(const name of ['measured','zero','home','positive','negative']){
      const button=document.getElementById(`pose-reference-${name}`);
      button.setAttribute('aria-pressed',String(mode===name));
      button.disabled=!hinge&&['positive','negative'].includes(name);
    }
    let poseLabel,badge;
    if(reference){
      const angle=view.referenceJoints?.[index]*180/Math.PI;
      poseLabel=mode==='home'?`HOME 站姿参考 · ID ${id} ${referenceAngle(officialStandingDegrees[id],2)}°`
        :mode==='zero'?'独立零位参考 · 14 个可动关节均为 0°'
        :`${mode==='positive'?'正向':'负向'}示范 · ID ${id}：0° → ${mode==='positive'?'+10°':'−10°'} · 当前 ${referenceAngle(angle,1)}°`;
      badge='模型参考';
    }else{
      const tilt=sample?.tiltStatus==='live'?'实时倾斜':view.lastGravity?'倾斜未更新，沿用旧值':'倾斜未知，机身暂按水平显示';
      poseLabel=sample?.live?`关节实测 · ${tilt}`:view.measuredPoseSeen?'反馈不完整或已过期 · 保留最后实测姿态':'零位示意 · 尚无完整的 14 关节实测反馈';
      badge=sample?.live?'关节实测':view.measuredPoseSeen?'旧姿态':'等待反馈';
    }
    set('pose-label',poseLabel);set('pose-badge',badge);
    document.getElementById('pose-badge').className='badge '+(reference?'reference':sample?.live?'':'warn');
    document.getElementById('pose-hud').hidden=reference;
    document.getElementById('ghost').disabled=reference||!sample?.targetJoints;
    document.getElementById('heat').disabled=reference;
    const identity=`ID ${id} · ${label}`;
    set('pose-reference-info',hinge
      ?`${identity}｜零位 0°｜HOME ${referenceAngle(officialStandingDegrees[id],2)}°`
      :`${identity}｜当前模型的嘴部固定，不能用 3D 开合判断方向；请看编码器与实物。`);
    const sampleNote=!reference&&!sample?.live&&sample?.missingIds?.length?`缺少有效角度：${sample.missingIds.join('、')}。`:'';
    set('pose-reference-detail',reference
      ?'仅屏幕示范，不控制舵机、不使用本机标定；正负向示范从全零位开始。'
      :`${sampleNote}实测图按已保存标定换算；核对方向请先看独立正向示范。`);
    const tiltText=sample?.tiltStatus==='live'?'实时重力 · 按已确认的机身坐标显示'
      :sample?.tiltStatus==='unverified'?`IMU 安装未确认 · ${view.lastGravity?'沿用上次倾斜':'机身暂按水平参考'}`
      :sample?.tiltStatus==='stale'?`IMU 已过期 · ${view.lastGravity?'沿用上次倾斜':'机身暂按水平参考'}`
      :'倾斜数据不可用 · 不代表机身水平';
    set('tilt-status',tiltText);
  }
}
