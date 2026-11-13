"""Validate an installed V160 upgrade, raw left-kick data and read-only roller display."""
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tarfile
import tomllib
import unittest
import zipfile
from html.parser import HTMLParser

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packaging'))
import model_packages as models
from configure import dumps

LEFT='ee0376c927044cdece056ba1d3e6eac7'
def previous_files():
    with zipfile.ZipFile(ROOT/'base/Microduck-Console-R17-V160.zip') as archive:
        name=next(n for n in archive.namelist() if n.endswith('/updates/Microduck-Robotd-FT6-R17.tar.gz'))
        raw=archive.read(name)
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
        return {name:archive.extractfile('Microduck-Robotd-FT6-R17/'+name).read()
                for name in ('robotd-profile.toml','management-profile.json')}

class Elements(HTMLParser):
    def __init__(self):super().__init__();self.roller=False;self.depth=0;self.controls=[];self.ids=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.append(attrs['id'])
        if 'roller-help' in attrs.get('class','').split():self.roller=True;self.depth=1
        elif self.roller and tag=='div':self.depth+=1
        if self.roller and (tag in ('button','input') or any(k.startswith('data-') for k in attrs)):
            self.controls.append((tag,attrs))
    def handle_endtag(self,tag):
        if self.roller and tag=='div':
            self.depth-=1
            if not self.depth:self.roller=False

class DeploymentTests(unittest.TestCase):
    def test_one_existing_query_reports_roller_installation_without_claiming_load(self):
        sys.path.insert(0,str(ROOT/'console'))
        sys.path.insert(0,str(ROOT/'console/verification'))
        from test_query_logs157 import Channel
        from service_control import ServiceController,ServiceTransport
        from system_log import SystemLog
        from telemetry import Store
        with tempfile.TemporaryDirectory() as directory:
            log=SystemLog(directory)
            try:
                data={'models':[],'slots':[],'roller_models':[
                    {'id':name,'name':name,'available':True} for name in ('swizzle','crouch','spin')]}
                transport=ServiceTransport('', '/unused', log);channel=transport.channel=Channel(data)
                store=Store('service');store.system_log=log
                store.snapshot=lambda:{'bus':{'build':'1fa8438-feetech-ft6-control.38'}}
                result=ServiceController(store,transport=transport,warm=False).models()
                self.assertEqual(result,data);self.assertEqual(len(channel.calls),1)
                self.assertEqual([row['source'] for row in log.tail()['entries']],['模型配置','滑轮模型'])
                log.flush();text=log.path.read_text()
                self.assertIn('已安装 3 个',text);self.assertIn('实体手柄切换后加载',text)
            finally:log.close()

    def test_original_left_model_and_mismatched_foot(self):
        directory=ROOT/'packaging/models'/LEFT
        files={n:(directory/n).read_bytes() for n in models.SOURCE_FILES if (directory/n).is_file()}
        files['policy.onnx']=(directory/'policy.onnx').read_bytes()
        info=models.validate_export(files)
        self.assertEqual(info['slot'],'kick_left')
        self.assertEqual(info['skill']['duration'],.5)
        self.assertFalse(info['skill']['chain'])
        self.assertEqual(hashlib.sha256(files['policy.onnx']).hexdigest()[:32],LEFT)
        bad=files.copy();contract=json.loads(files['deployment-contract.json'])
        contract['role']='kick_right';bad['deployment-contract.json']=json.dumps(contract).encode()
        with self.assertRaises(ValueError):models.validate_export(bad)

    def test_v160_upgrade_adds_lb_without_resetting_saved_parameters(self):
        previous=previous_files()
        original=tomllib.loads(previous['robotd-profile.toml'].decode())
        original['policy'].update(action_scale=.63,head_lowpass=.42,legs_lowpass=.65)
        original['pad']['rb']='operator_custom_right'
        old_paths={k:original['policy'][k] for k in ('walk','sitstand','ground_pick','roulade','kick_right')}
        with tempfile.TemporaryDirectory() as tmp:
            old=Path(tmp)/'previous';old.mkdir()
            for name,raw in previous.items():(old/name).write_bytes(raw)
            source=Path(tmp)/'saved.toml';output=Path(tmp)/'new.toml';source.write_text(dumps(original))
            command=[sys.executable,str(ROOT/'packaging/configure.py'),'--source',str(source),
                '--overrides',str(ROOT/'packaging/robotd-profile.toml'),'--previous-overrides',
                str(old/'robotd-profile.toml'),'--output',str(output)]
            subprocess.run(command,check=True,capture_output=True,text=True)
            current=tomllib.loads(output.read_text())
            self.assertEqual(current['policy']['kick_left'],f'/opt/robot/feetech-ft5-r5/models/{LEFT}/policy.onnx')
            self.assertEqual({k:current['policy'][k] for k in old_paths},old_paths)
            self.assertEqual(current['policy']['action_scale'],.63)
            self.assertEqual(current['policy']['head_lowpass'],.42)
            self.assertEqual(current['policy']['legs_lowpass'],.65)
            self.assertEqual(current['pad']['lb'],'kick_left')
            self.assertEqual(current['pad']['rb'],'operator_custom_right')
            skill=[s for s in current['policy']['skill'] if s['name']=='kick_left']
            self.assertEqual(len(skill),1);self.assertEqual(skill[0]['duration'],.5)
            skill[0]['params']['action_scale']=.82
            source.write_text(dumps(current))
            command[command.index('--previous-overrides')+1]=str(ROOT/'packaging/robotd-profile.toml')
            subprocess.run(command,check=True,capture_output=True,text=True)
            reinstalled=tomllib.loads(output.read_text())
            self.assertEqual(next(s for s in reinstalled['policy']['skill'] if s['name']=='kick_left')['params']['action_scale'],.82)

    def test_roller_catalogue_is_read_only_and_not_reported_as_loaded(self):
        base=ROOT/'packaging'
        before={p:p.read_bytes() for p in (base/'roller').rglob('*') if p.is_file()}
        data=models.catalog(base,base/'robotd-profile.toml')
        self.assertEqual(len(data['models']),6)
        self.assertEqual([r['id'] for r in data['roller_models']],['swizzle','crouch','spin','standup'])
        self.assertTrue(all(r['available'] and 'active' not in r for r in data['roller_models']))
        self.assertEqual(before,{p:p.read_bytes() for p in before})

    def test_roller_help_contains_no_browser_controls_or_duplicate_ids(self):
        html=(ROOT/'console/static/index.html').read_text();parser=Elements();parser.feed(html)
        self.assertFalse(parser.controls)
        self.assertEqual(len(parser.ids),len(set(parser.ids)))
        for text in ('滑轮 · ↑ 长按 3 秒','滑轮 · ← 长按 2 秒','滑轮 · A','IMU 航向反馈'):
            self.assertIn(text,html)
        self.assertNotIn('当前没有左踢模型',html)

if __name__=='__main__':unittest.main()
