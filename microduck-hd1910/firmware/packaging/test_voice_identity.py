"""System ALSA migration and saved volume, with no real soundcard/systemd writes."""
import importlib.util,json,os,subprocess,tempfile,tomllib,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import voice_preferences
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('system_audio_setup',ROOT/'packaging/voice-setup.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
class SystemAudioTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.system=self.base/'system'
  self.params=self.base/'robotd.toml';self.bank=self.base/'voice-bank';self.bank.mkdir();(self.bank/'.seed').write_text('1:5')
  self.params.write_text('[audio]\ndevice="microduck_voice"\nbank='+json.dumps(str(self.bank))+'\n')
  self.setup=self.base/'voice-device.json';self.setup.write_text(json.dumps({'card':'aic3104','slave':'plughw:aic3104','preferences_uid':0,'preferences_path':'/root/.local/state/microduck-r17/voice-volume.json'}))
  self.user=SimpleNamespace(pw_name='radxa',pw_uid=1000,pw_gid=1000,pw_dir=str(self.base/'user'))
  self.current=127;self.muted=False;self.legacy=566;self.commands=[]
 def tearDown(self):self.temp.cleanup()
 def runner(self,argv,**kwargs):
  self.commands.append(argv)
  if 'ensure-bank' in argv:(self.bank/'.seed').write_text('1:5')
  if 'name=Microduck Voice Playback Volume' in argv:
   if self.legacy is None:raise subprocess.CalledProcessError(1,argv,stderr='No such control')
   return SimpleNamespace(returncode=0,stdout=f': values={self.legacy}',stderr='')
  if 'name=PCM Playback Volume' in argv:
   if 'cset' in argv:self.current=int(argv[-1])
   return SimpleNamespace(returncode=0,stdout=f': values={self.current},{self.current}',stderr='')
  if 'name=Line Playback Switch' in argv:
   if 'cset' in argv:self.muted=argv[-1]=='off,off'
   return SimpleNamespace(returncode=0,stdout=': values='+('off,off' if self.muted else 'on,on'),stderr='')
  if 'store' in argv:
   state=self.system/'var/lib/alsa/asound.state';state.parent.mkdir(parents=True,exist_ok=True);state.write_text(f'{self.current},{self.muted}')
  return SimpleNamespace(returncode=0,stdout='',stderr='')
 def install(self):
  with patch.object(helper,'BASE',self.base),patch.object(helper,'ROOT',self.system),patch.object(helper,'seed',return_value=(1,'test')),patch.object(helper.shutil,'which',return_value='/usr/sbin/alsactl'),patch.object(helper.subprocess,'run',self.runner),patch.dict(os.environ,{'SUDO_USER':'radxa'}),patch.object(helper.pwd,'getpwnam',return_value=self.user):helper.setup(self.params)
 def test_legacy_loudness_migrates_to_hardware_pcm_and_system_state_without_home_json(self):
  self.install()
  self.assertEqual(self.current,voice_preferences.raw(5));self.assertFalse(self.muted)
  data=tomllib.loads(self.params.read_text());self.assertEqual(data['audio']['device'],'plughw:aic3104')
  device=json.loads(self.setup.read_text());self.assertNotIn('preferences_path',device);self.assertEqual(device['control'],'PCM Playback Volume')
  rule=self.system/'etc/sudoers.d/microduck-alsa-volume'
  self.assertEqual(rule.read_text(),'radxa ALL=(root) NOPASSWD: /usr/sbin/alsactl store aic3104\n');self.assertEqual(rule.stat().st_mode&0o777,0o440)
  self.assertTrue((self.system/'var/lib/alsa/asound.state').is_file());self.assertFalse((self.base/'user').exists())
  for unit in ('alsa-restore.service','alsa-state.service'):
   text=(self.system/f'etc/systemd/system/{unit}.d/microduck-audio.conf').read_text()
   self.assertIn('After=aic3104-init.service',text);self.assertIn('Before=robotd.service',text)
  self.assertFalse(any(a[0] in ('aplay',) or 'restore' in a or 'daemon-reload' in a for a in self.commands))
 def test_repeat_install_does_not_initialize_sound_read_mixer_or_rewrite_volume(self):
  self.install();before=self.params.read_bytes();self.current=43;self.commands.clear()
  self.install()
  self.assertEqual(self.commands,[]);self.assertEqual(self.current,43);self.assertEqual(self.params.read_bytes(),before)
 def test_first_install_builds_missing_bank_once_and_uses_descriptor_default(self):
  self.legacy=None;(self.bank/'.seed').unlink()
  with patch.object(voice_preferences,'DEFAULT_VOLUME',23):self.install()
  self.assertEqual(self.current,voice_preferences.raw(23));self.assertEqual(sum('ensure-bank' in a for a in self.commands),1)
  self.commands.clear();self.install();self.assertEqual(self.commands,[])
 def test_existing_system_volume_is_kept_without_reset_to_default(self):
  self.legacy=None;self.current=76;state=self.system/'var/lib/alsa/asound.state';state.parent.mkdir(parents=True);state.write_text('existing state')
  self.install();self.assertEqual(self.current,76)
  self.assertFalse(any('cset' in a for a in self.commands))
 def test_mute_migrates_and_os_restore_precedes_robotd_without_startup_audio_hook(self):
  self.legacy=0;self.install();self.assertTrue(self.muted)
  import runtime
  unit=runtime.unit('motion');self.assertIn('After=alsa-restore.service alsa-state.service',unit)
  self.assertNotIn('voice-setup.py',unit);self.assertNotIn('ALSA_CONFIG_PATH=',unit)
if __name__=='__main__':unittest.main()
