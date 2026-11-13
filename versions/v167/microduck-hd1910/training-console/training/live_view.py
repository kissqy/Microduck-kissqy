"""Read-only snapshots from the training env; rendering runs in a CPU child.

No policy is loaded, no extra environment is stepped and no training state is
written. A disconnected/failed viewer must never raise into the training loop.
"""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time

if __package__:
    from .event_protocol import emit, split_output
    from .sample_alignment import progress as sample_progress
else:
    from event_protocol import emit, split_output
    from sample_alignment import progress as sample_progress

VIEW_COUNT = 9


def selected_indices(start, num_envs):
    count=min(VIEW_COUNT,num_envs)
    start=max(0,min(int(start),num_envs-count))
    return list(range(start,start+count))


def display_positions(frame):
    """Compact display translation only; never modify the simulation tensors."""
    import numpy as np
    positions=np.asarray(frame['xpos'],dtype=float).copy()
    count=len(positions);cols=min(3,count);rows=(count+cols-1)//cols
    offsets=np.array([((i%cols-(cols-1)/2)*.7,((rows-1)/2-i//cols)*.7,0.) for i in range(count)])
    positions-=np.asarray(frame['origins'])[:,None,:]
    positions+=offsets[:,None,:]
    return positions,offsets


def reset_summary(env):
    """Read the live EventManager, whose parameters the official curriculum mutates."""
    result={'episode_limit_s':float(env.cfg.episode_length_s)} if hasattr(env,'cfg') else {}
    manager=getattr(env,'event_manager',None)
    if manager:
        for event in ('set_ground_state','random_prone_init','set_roulade_state'):
            try:
                params=manager.get_term_cfg(event).params
                keys={'set_ground_state':('face_down_prob','face_up_prob','sitting_prob','standing_prob'),
                      'random_prone_init':('prone_prob','crouch_prob','face_down_prob','side_prob'),
                      'set_roulade_state':('standing_prob','midroll_prob')}[event]
                mix={key:float(params.get(key,0)) for key in keys}
                result.update(reset_event=event,reset_params=mix)
                if event in ('set_ground_state','set_roulade_state'):
                    total=sum(mix.values())
                    if total>0:result['reset_mix']={key:value/total for key,value in mix.items()}
                break
            except (KeyError,ValueError,AttributeError):pass
    return result


def atomic_json(path, value):
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,separators=(',',':'),allow_nan=False),encoding='utf-8')
    os.replace(tmp,path)


class TrainingLiveView:
    def __init__(self, env, report=emit):
        import mujoco
        self.env,self.report=env,report
        self.index=0;self.watching=False;self.last_capture=0.0;self.failed=False
        self.stop=threading.Event();self.frames=queue.Queue(maxsize=1)
        self.directory=Path(tempfile.mkdtemp(prefix='microduck-training-live-'))
        self.proc=None
        try:
            mujoco.mj_saveModel(env.sim.mj_model,str(self.directory/'model.mjb'),None)
            self.proc=subprocess.Popen([sys.executable,'-u',str(Path(__file__).resolve()),'--serve',
                str(self.directory),str(env.num_envs),str(os.getpid())],stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                env={**os.environ,'CUDA_VISIBLE_DEVICES':''})
            self.reader=threading.Thread(target=self._relay_output,daemon=True);self.reader.start()
            self.writer=threading.Thread(target=self._transfer,daemon=True);self.writer.start()
        except Exception:
            self.close();raise

    def _relay_output(self):
        # The renderer must not write directly into the trainer's stdout pipe.
        # Re-emit complete frames using the parent's shared message writer.
        try:
            for raw in self.proc.stdout:
                line=raw.decode('utf-8',errors='replace').rstrip('\r\n')
                for category,value in split_output(line):
                    if category=='event':
                        event=dict(value);kind=event.pop('kind')
                        self.report(kind,**event)
                    else:self.report('log',line=value)
        except Exception as error:
            if not self.stop.is_set():self.fail(error)
        finally:self.proc.stdout.close()

    def _transfer(self):
        try:
            while not self.stop.is_set():
                try:
                    selected=json.loads((self.directory/'selection.json').read_text())
                    self.index=selected_indices(selected['index'],self.env.num_envs)[0]
                    self.watching=bool(selected['watching'])
                except (OSError,ValueError,KeyError):self.watching=False
                try:frame=self.frames.get(timeout=.05)
                except queue.Empty:continue
                atomic_json(self.directory/'frame.json',frame)
        except Exception as error:self.fail(error)

    def fail(self,error):
        if self.failed:return
        self.failed=True;self.watching=False
        self.report('training_view_error',message='训练画面不可用，训练继续：'+type(error).__name__+': '+str(error))

    def capture(self):
        # Curriculum diagnostics are independent of watching and never copy GPU
        # state. Report the EventManager values, not the configuration defaults.
        now=time.monotonic()
        if not self.stop.is_set() and now-getattr(self,'last_diagnostic',0)>1:
            self.last_diagnostic=now
            try:
                self.report('training_curriculum_state',data={
                    'step':int(self.env.common_step_counter),'captured_at':time.time(),
                    **sample_progress(self.env),**reset_summary(self.env)})
            except Exception:pass
        if self.failed or self.stop.is_set():return
        if self.proc.poll() is not None:
            self.fail('只读画面进程已退出（%s）'%self.proc.returncode);return
        if not self.watching or now-self.last_capture<.05:return
        self.last_capture=now
        try:
            indices=selected_indices(self.index,self.env.num_envs)
            idx=indices[0];end=indices[-1]+1;data=self.env.sim.data
            # Slice on GPU BEFORE copying: never transfer all parallel worlds.
            xpos=data.xpos[idx:end].detach().cpu().numpy().copy()
            xmat=data.xmat[idx:end].detach().cpu().numpy().copy()
            origins=getattr(getattr(self.env,'scene',None),'env_origins',None)
            origins=(origins[idx:end].detach().cpu().numpy().copy().tolist() if origins is not None
                     else [[0.,0.,0.] for _ in indices])
            lengths=getattr(self.env,'episode_length_buf',None)
            elapsed=(lengths[idx:end].detach().cpu().numpy()*self.env.step_dt).tolist() if lengths is not None else None
            frame={'index':idx,'step':int(self.env.common_step_counter),
                'simulation_seconds':float(self.env.common_step_counter*self.env.step_dt),
                'captured_at':time.time(),'xpos':xpos.tolist(),'xmat':xmat.tolist(),
                'env_indices':indices,'origins':origins,'episode_seconds':elapsed,**reset_summary(self.env)}
            try:self.frames.put_nowait(frame)
            except queue.Full:
                try:self.frames.get_nowait()
                except queue.Empty:pass
                self.frames.put_nowait(frame)
        except Exception as error:self.fail(error)

    def close(self):
        self.stop.set();self.watching=False
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:self.proc.wait(timeout=.5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                try:self.proc.wait(timeout=.5)
                except subprocess.TimeoutExpired:pass
        reader=getattr(self,'reader',None)
        if reader:reader.join(timeout=.2)
        writer=getattr(self,'writer',None)
        if writer:writer.join(timeout=.2)
        if not writer or not writer.is_alive():shutil.rmtree(self.directory,ignore_errors=True)


def install_training_view(official,report=emit,observer_factory=TrainingLiveView,on_first_step=None):
    """Instrument the official env class while preserving run_train/runner/learn."""
    original=getattr(official,'ManagerBasedRlEnv',None)
    if original is None:
        report('training_view_error',message='当前训练入口未暴露环境实例，无法接入现场画面；训练继续。')
        return lambda:None
    observers=[]
    class ObservedEnv(original):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs);self._training_live=None
            self._first_step_reported=False
            if int(os.environ.get('RANK','0'))==0:
                try:
                    self._training_live=observer_factory(self,report)
                    observers.append(self._training_live)
                except Exception as error:report('training_view_error',message='训练画面启动失败，训练继续：'+str(error))
        def step(self,*args,**kwargs):
            result=super().step(*args,**kwargs)
            if not self._first_step_reported:
                self._first_step_reported=True
                if on_first_step is not None and int(os.environ.get('RANK','0'))==0:
                    try:on_first_step(self,report)
                    except Exception as error:
                        report('log',line='训练参数读回暂不可用，训练继续：'+str(error))
            if self._training_live:self._training_live.capture()
            return result
        def close(self):
            if self._training_live:self._training_live.close()
            return super().close()
    official.ManagerBasedRlEnv=ObservedEnv
    def restore():
        official.ManagerBasedRlEnv=original
        for observer in observers:observer.close()
    return restore


def serve(directory,num_envs,parent_pid):
    # The renderer never imports torch or owns CUDA. Exit if training disappears.
    import ctypes
    import signal
    if sys.platform=='linux':
        ctypes.CDLL(None).prctl(1,signal.SIGTERM)
        if os.getppid()!=parent_pid:return
    import mujoco
    import numpy as np
    import viser
    from mjviser import ViserMujocoScene
    model=mujoco.MjModel.from_binary_path(str(directory/'model.mjb'))
    server=viser.ViserServer(host='127.0.0.1',port=8093,label='训练现场 · Live training')
    try:
        count=min(VIEW_COUNT,num_envs)
        scene=ViserMujocoScene(server,model,num_envs=count)
        scene.show_only_selected=False;scene.camera_tracking_enabled=False
        pick=server.gui.add_number('起始编号 / First environment',initial_value=1,min=1,max=num_envs-count+1,step=1)
        previous_group=server.gui.add_button('上一组 / Previous group')
        next_group=server.gui.add_button('下一组 / Next group')
        @previous_group.on_click
        def previous_clicked(_):pick.value=max(1,int(pick.value)-count)
        @next_group.on_click
        def next_clicked(_):pick.value=min(num_envs-count+1,int(pick.value)+count)
        previous_group.disabled=next_group.disabled=num_envs<=count
        status=server.gui.add_html('等待当前训练采样…')
        mix_status=server.gui.add_html('')
        labels=[server.scene.add_label('/training_env_'+str(i),'等待采样',position=(0,0,.35)) for i in range(count)]
        server.gui.add_markdown(f'同时观察 {count} 个实际训练环境，编号固定，不筛选成功样本。仅为显示并排排列；最多20帧/秒，可能跳过短暂动作。')
        @server.on_client_connect
        def connected(client):
            client.camera.position=(1.5,-2.1,1.9) if count>1 else (.55,-.55,.35)
            if count>1:client.camera.fov=.7853981633974483
            client.camera.look_at=(0,0,.1)
            client.camera.up_direction=(0,0,1)
        emit('training_view_ready',url='http://127.0.0.1:'+str(server.get_port()),num_envs=num_envs)
        previous=None;last_report=0.0;last_control=0.0
        while os.getppid()==parent_pid:
            indices=selected_indices(int(pick.value)-1,num_envs);index=indices[0]
            if time.monotonic()-last_control>.2:
                atomic_json(directory/'selection.json',{'index':index,'watching':bool(server.get_clients())})
                last_control=time.monotonic()
            try:frame=json.loads((directory/'frame.json').read_text())
            except (OSError,ValueError):time.sleep(.05);continue
            key=(frame['index'],frame['step'])
            matching=frame.get('env_indices')==indices
            if matching and key!=previous:
                positions,offsets=display_positions(frame)
                scene.update_from_arrays(positions.reshape(count,model.nbody,3),
                    np.asarray(frame['xmat']).reshape(count,model.nbody,3,3),env_idx=0)
                for i,label in enumerate(labels):
                    elapsed=frame.get('episode_seconds')
                    label.position=tuple(offsets[i]+np.array([0.,0.,.4]))
                    label.text=f'鸭子 {indices[i]+1}'+(f' · 回合 {elapsed[i]:.1f}s' if elapsed is not None else '')
                    label.visible=True
                previous=key
            age=time.time()-frame['captured_at']
            if time.monotonic()-last_report>1:
                waiting=not matching
                if waiting:
                    for label in labels:label.visible=False
                status.content=('正在切换鸭子…' if waiting else
                    f"鸭子 {index+1}–{indices[-1]+1} / {num_envs} · 训练步 {frame['step']} · "+
                    (f'距上次采样 {age:.1f} 秒' if age>1 else '实时采样'))
                mix=frame.get('reset_mix',{})
                names={'face_down_prob':'趴地','face_up_prob':'仰躺/侧倾','sitting_prob':'坐姿','standing_prob':'站姿','midroll_prob':'翻滚中途姿态'}
                mix_status.content=('回合上限 '+str(frame['episode_limit_s'])+' 秒。' if frame.get('episode_limit_s') else '')+(
                    '当前复位概率：'+' / '.join(names[k]+f' {v:.0%}' for k,v in mix.items()) if mix else '')
                emit('training_view_state',data={'env_index':index,'env_indices':indices,'view_count':count,'num_envs':num_envs,
                    'step':frame['step'],'captured_at':frame['captured_at'],'waiting':waiting})
                last_report=time.monotonic()
            time.sleep(.025)
    finally:server.stop()


if __name__=='__main__':
    try:serve(Path(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4]))
    except Exception as error:
        emit('training_view_error',message='训练画面不可用，训练继续：'+type(error).__name__+': '+str(error))
        raise
