#!/usr/bin/env python3
"""Independent Python ONNX reference for the encoder-side 61/14 teacher."""
import json,math
from pathlib import Path
import numpy as np
import onnxruntime as ort

root=Path(__file__).resolve().parents[1]
model=root/'policies/walk'
contract=json.loads((model/'deployment-contract.json').read_text())
runtime=json.loads((model/'deployment-runtime.json').read_text())
names=contract['onnx_metadata']['joint_names'].split(',')
home14=[next(j['home_rad'] for j in contract['model']['joints'] if j['name']==n) for n in names]
home=np.array(home14[:9]+[0.]+home14[9:],dtype=np.float64)
session=ort.InferenceSession(str(model/'policy.onnx'),providers=['CPUExecutionProvider'])
settings=contract['required_policy_settings'];frames=[];last=np.zeros(14,dtype=np.float32);previous=None
for tick in range(64):
    reset=tick in (0,23,47)
    if reset:last[:]=0;previous=None
    positions=home+np.array([.025*math.sin(tick*.17+j) for j in range(15)])
    velocity=[.12*math.cos(tick*.13+j) for j in range(15)]
    gyro=[.1*math.sin(tick*.09),.08*math.cos(tick*.11),.02]
    gravity=[.05*math.sin(tick*.1),.04*math.cos(tick*.1),-.997]
    requested_twist=[[.3,0.,0.],[-.3,0.,0.],[0.,.2,0.],[0.,0.,.8],[0.,0.,0.]][(tick//5)%5]
    requested_head=[.3*math.sin(tick*.03+i) for i in range(4)]
    requested_body=[.003*math.sin(tick*.2),.03*math.cos(tick*.1),.02*math.sin(tick*.1)]
    twist=[float(np.clip(v,*contract['commands']['twist']['ranges'][k])) for v,k in zip(requested_twist,('lin_vel_x','lin_vel_y','ang_vel_z'))]
    head=[float(np.clip(v,*r)) for v,r in zip(requested_head,runtime['commands']['head_pose'])]
    body=[float(np.clip(v,*runtime['commands']['body_pose'][i])) for v,i in zip(requested_body,(2,3,4))]
    q=[positions[i]-home[i] for i in range(15) if i!=9]
    dq=[velocity[i] for i in range(15) if i!=9]
    observation=np.array(gyro+gravity+q+dq+list(last)+twist+head+[0.,0.,body[0],body[1],body[2],0.],dtype=np.float32)[None,:]
    raw=session.run(None,{'obs':observation})[0][0];last=raw.copy()
    offset=np.array(list(raw[:9])+[0.]+list(raw[9:]),dtype=np.float64)
    targets=home+settings['action_scale']*offset
    if previous is not None:
        for j in range(15):
            alpha=settings['head_lowpass'] if 5<=j<=8 else 1. if j==9 else settings['legs_lowpass']
            targets[j]=alpha*targets[j]+(1-alpha)*previous[j]
    previous=targets.copy()
    frames.append({'reset':reset,'positions':positions.tolist(),'velocities':velocity,'gyro':gyro,'gravity':gravity,'twist':requested_twist,'head':requested_head,'body':requested_body,'targets':targets.tolist(),'raw_actions':raw.tolist()})
output=root/'robotd/test-data/filtered-teacher-reference.json'
output.write_text(json.dumps(frames,separators=(',',':'))+'\n')
print(json.dumps({'frames':len(frames),'model':contract['task'],'settings':settings,'output':str(output)}))
