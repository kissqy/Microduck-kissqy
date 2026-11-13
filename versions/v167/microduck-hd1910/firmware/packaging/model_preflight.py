#!/usr/bin/env python3
"""Validate model changes before stopping the running service. No writes."""
import sys, pathlib, subprocess
from model_packages import catalog, verify_directory, check_calibration, selected_config, runtime_environment, SLOTS, BASE, CALIBRATION

def preflight(action,ident,slot=None):
 listing=catalog();row=next((r for r in listing['models'] if r['id']==ident),None)
 if not row or not row.get('available'):raise ValueError('模型不存在或文件损坏')
 selected=verify_directory(pathlib.Path(row['path']).parent);check_calibration(selected)
 if action=='model-assign' and (slot not in SLOTS or selected['slot']!=slot):raise ValueError('所选动作与模型部署合同不一致，未停止服务')
 if action=='model-delete' and row.get('active') and row['slot']=='walk':
  other=next((r for r in listing['models'] if r.get('slot')=='walk' and r.get('available') and r['id']!=ident),None)
  if not other:raise ValueError('至少保留一份可用行走模型；请先导入另一份行走模型')
  selected=verify_directory(pathlib.Path(other['path']).parent);check_calibration(selected)
 if action in ('model-assign','model-check'):
  cfg=selected_config()
  for slot in SLOTS:
   path=cfg.get('policy',{}).get(slot)
   if slot!=row['slot'] and path and path!='none':
    other=verify_directory(pathlib.Path(path).parent)
    if other['firmware_p']!=selected['firmware_p']:raise ValueError('各动作模型的 BAM 固件 P 不一致')
 if action in ('model-assign','model-check') or row.get('active'):
  result=subprocess.run([str(BASE/'robotd'),'validate-policy',str(BASE/'models'/selected['id']/'policy.onnx')],env=runtime_environment(),capture_output=True,text=True,timeout=45)
  if result.returncode:raise ValueError('模型预检查失败：'+(result.stderr or result.stdout)[-1200:])

if __name__=='__main__':
 try:preflight(*sys.argv[1:])
 except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
