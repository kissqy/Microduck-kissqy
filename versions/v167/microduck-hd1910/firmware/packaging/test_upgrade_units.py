"""Run the shipped Bash functions with missing units and failed stops, without systemd."""
import json,os,shlex,subprocess,sys,tempfile,unittest
from pathlib import Path
SCRIPT=Path(__file__).with_name('service.sh')
PREFIX=SCRIPT.read_text().split('if [[ ${1:-} == models',1)[0]
FAKE='''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
p=Path(os.environ['UNIT_STATE']);data=json.loads(p.read_text());args=sys.argv[1:]
with open(os.environ['UNIT_CALLS'],'a') as out:out.write(json.dumps(args)+'\\n')
a=args[0];unit=args[1] if len(args)>1 else '';u=data.get(unit,{'load':'not-found','active':'inactive'})
if a=='cat':sys.exit(0) # This reproduces the old incorrect file-presence check.
if a=='show':
 if u.get('query_fail'):
  print('Failed to connect to bus: Permission denied',file=sys.stderr);sys.exit(13)
 props=[args[i+1] for i,x in enumerate(args) if x=='-p']
 for prop in props:
  key={'LoadState':'load','ActiveState':'active','ExecStart':'exec','MainPID':'main_pid','ControlPID':'control_pid'}.get(prop,prop)
  value=u.get(key,0 if prop in ('MainPID','ControlPID') else '')
  print(value if '--value' in args else prop+'='+str(value))
 sys.exit(u.get('query_rc',0))
if a=='stop':
 rc=u.get('stop_rc',0)
 if u.get('disappear'):
  u.update(load='not-found',active='inactive',main_pid=0,control_pid=0,query_rc=4);rc=5
 if u.get('stopped_but_loaded'):
  u.update(active='inactive',main_pid=0,control_pid=0);rc=5
 if not rc and not u.get('stop_no_effect'):
  u.update(active='inactive',main_pid=0,control_pid=0)
 data[unit]=u;p.write_text(json.dumps(data))
 if rc:print('Failed to stop '+unit+': Unit '+unit+' not loaded.' if rc==5 else 'Stop failed for '+unit,file=sys.stderr)
 sys.exit(rc)
if a in ('start','restart'):
 for name in args[1:]:
  v=data.get(name,{});v['active']='active';data[name]=v
 p.write_text(json.dumps(data));sys.exit(0)
if a in ('daemon-reload','reset-failed'):sys.exit(0)
sys.exit(0)
'''
class UpgradeUnitTests(unittest.TestCase):
 def run_script(self,units,body,prefix=PREFIX):
  with tempfile.TemporaryDirectory() as temp:
   r=Path(temp);(r/'service-prefix.sh').write_text(prefix);(r/'systemctl').write_text(FAKE);(r/'systemctl').chmod(0o755)
   state=r/'state.json';calls=r/'calls';state.write_text(json.dumps(units))
   env={**os.environ,'PATH':str(r)+os.pathsep+os.environ['PATH'],'UNIT_STATE':str(state),'UNIT_CALLS':str(calls),'TEST_ROOT':str(r),'SERVICE_SRC':str(SCRIPT.resolve().parent),'REAL_PYTHON':sys.executable}
   result=subprocess.run(['bash','-c','source '+shlex.quote(str(r/'service-prefix.sh'))+'\n'+body],env=env,capture_output=True,text=True)
   rows=[json.loads(x) for x in calls.read_text().splitlines()] if calls.exists() else []
   return result,rows,json.loads(state.read_text())
 def active(self,**extra):return {'load':'loaded','active':'active',**extra}
 def missing(self):return {'load':'not-found','active':'inactive','query_rc':4}
 def test_restart_success_requires_control_readiness_without_retrying_process(self):
  # A live IPC socket alone must not report a dead control loop as recovered.
  for ready_rc in (0,19):
   with self.subTest(ready_rc=ready_rc):
    body='python3() { [[ ${1##*/} == startup_gate.py ]] || return 90; echo READINESS-CHECK; return '+str(ready_rc)+'; }\nrestart_service\necho RESTART-COMPLETED\n'
    result,calls,_=self.run_script({'robotd.service':self.active()},body)
    self.assertEqual(result.returncode,0 if ready_rc==0 else 78,result.stderr)
    self.assertEqual(calls.count(['restart','robotd.service']),1)
    self.assertEqual(result.stdout.count('READINESS-CHECK'),1)
    self.assertEqual('RESTART-COMPLETED' in result.stdout,ready_rc==0)
 def test_corrupt_bundle_is_rejected_before_stopping_any_service(self):
  body=r'''bundle_dir="$TEST_ROOT"
identity() { echo IDENTITY-CHECK; }
python3() {
 [[ ${1##*/} == elf_integrity.py ]] || return 90
 echo ELF-REJECTED
 return 23
}
install_bundle upgrade
echo UNEXPECTED-INSTALL
'''
  units={u:self.active() for u in ('robotd.service','padd.service','gamesir-xboxd.service','microduck-webpad.service','microduck-webpad.socket')}
  result,calls,state=self.run_script(units,body)
  self.assertEqual(result.returncode,23,result.stderr)
  self.assertIn('IDENTITY-CHECK',result.stdout);self.assertIn('ELF-REJECTED',result.stdout)
  self.assertNotIn('UNEXPECTED-INSTALL',result.stdout)
  self.assertFalse(any(c[0] in ('stop','start','restart') for c in calls))
  self.assertTrue(all(u['active']=='active' for u in state.values()))
 def test_complete_installer_recovers_missing_input_units_without_motion(self):
  body=r'''bundle_dir="$TEST_ROOT"
install_dir="$TEST_ROOT"
config_dir="$TEST_ROOT/config"
params_path="$config_dir/robotd.toml"
calibration_path="$config_dir/calibration.toml"
service_user=$(id -un)
service_group=$(id -gn)
touch "$install_dir/robotd" "$install_dir/service.sh"
cp "$SERVICE_SRC/configure.py" "$bundle_dir/configure.py"
cp "$SERVICE_SRC/management_profile.py" "$bundle_dir/management_profile.py"
cp "$SERVICE_SRC/robotd-profile.toml" "$bundle_dir/robotd-profile.toml"
cp "$SERVICE_SRC/management-profile.json" "$bundle_dir/management-profile.json"
identity() { :; }
write_dropin() { :; }
restart_service() { systemctl restart robotd.service; }
request_relax_service() { echo RELAX-REQUEST; }
python3() {
 case "${1##*/}" in
 package-preflight.py) echo UNEXPECTED-PREFLIGHT; return 87 ;;
 elf_integrity.py) echo ELF-INTEGRITY-CHECK ;;
 rebuild-config.py) printf '[policy]\n' > "$3/robotd.toml"; printf 'motion_enabled = false\n' > "$3/hd1910-calibration.toml" ;;
 configure.py) "$REAL_PYTHON" "$@" ;;
 calibration-config.py) cp "$3" "$5" ;;
 runtime.py) [[ $2 == configure-startup || $2 == disable-automatic-recovery ]] || { echo UNEXPECTED-READBACK; return 88; } ;;
 voice-setup.py) : ;;
 gamepad.py) [[ $2 == prepare-all ]] || return 89 ;;
 *) "$REAL_PYTHON" "$@" ;;
 esac
}
install_bundle upgrade
echo FULL-INSTALL-FINISHED
'''
  for load,active,robot_active in [('not-found','inactive','active'),('loaded','inactive','inactive'),('loaded','failed','inactive'),('masked','inactive','inactive'),('loaded','active','active')]:
   with self.subTest(load=load,active=active,robot=robot_active):
    units={u:{'load':load,'active':active,'query_rc':4 if load=='not-found' else 0,'stop_rc':5} for u in ('microduck-webpad.socket','microduck-webpad.service','padd.service','gamesir-xboxd.service')}
    units['robotd.service']={'load':'loaded','active':robot_active,'exec':'official robotd'}
    result,calls,state=self.run_script(units,body)
    self.assertEqual(result.returncode,0,result.stderr);self.assertIn('FULL-INSTALL-FINISHED',result.stdout)
    for unit in ('padd.service','gamesir-xboxd.service'):
     self.assertTrue(any(c[0]=='stop' and unit in c for c in calls))
     self.assertEqual(sum(c[0]=='restart' and unit in c for c in calls),1)
     self.assertEqual(state[unit]['active'],'active')
    self.assertFalse(any('microduck-webpad.service' in c or 'microduck-webpad.socket' in c for c in calls))
    self.assertIn(['stop','robotd.service'],calls);self.assertIn(['restart','robotd.service'],calls)
    main=calls.index(['restart','robotd.service'])
    self.assertTrue(all(calls.index(c)>main for c in calls if c[0]=='restart' and 'padd.service' in c))
    self.assertIn('未请求运动',result.stdout)
    self.assertEqual(calls.count(['daemon-reload']),2)
    self.assertFalse(any(x[0]=='show' and any(v in ('LoadState','ActiveState','MainPID','ControlPID') for v in x) for x in calls))



if __name__=='__main__':unittest.main()
