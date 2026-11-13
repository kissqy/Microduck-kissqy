import json
from pathlib import Path
from html.parser import HTMLParser
import sys, unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packaging'))
import model_packages
class Structure(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.parents={};self.ids=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs);key=attrs.get('id') or attrs.get('class','')
        if attrs.get('id'):self.ids.append(attrs['id'])
        if key in ('model-management-anchor','pad-help','runtime-parameters'):
            self.parents[key]=[x[1] for x in self.stack]
        if tag not in ('input','img','br','hr','meta','link','source','path','circle','rect','i'):
            self.stack.append((tag,key))
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:self.stack=self.stack[:i];break
class CurrentLayout(unittest.TestCase):
    def test_models_and_parameters_share_column_with_reference_as_sibling(self):
        parser=Structure();parser.feed((ROOT/'console/static/index.html').read_text())
        for child in ('model-management-anchor','runtime-parameters'):
            self.assertIn('pad-model-parameters',parser.parents[child])
        self.assertNotIn('pad-model-parameters',parser.parents['pad-help'])
        self.assertIn('pad-configuration-column',parser.parents['pad-help'])
        self.assertEqual(len(parser.ids),len(set(parser.ids)))
    def test_all_roller_coefficients_and_manual_stand_are_reported(self):
        data=model_packages.catalog(ROOT/'packaging',ROOT/'packaging/robotd-profile.toml')
        rollers={r['id']:r for r in data['roller_models']}
        self.assertEqual(set(rollers),{'swizzle','crouch','spin','standup'})
        for name,row in rollers.items():
            self.assertTrue(row['available']);self.assertNotIn('active',row)
            self.assertEqual((row['action_scale'],row['head_lowpass'],row['legs_lowpass']),
                (.8,.5,.7) if name=='crouch' else (1.,1.,1.))
        self.assertFalse(rollers['standup']['trigger_bound'])
        self.assertEqual(rollers['standup']['checkpoint'],11000)
        contract=json.loads((ROOT/'packaging/roller/standup/deployment-contract.json').read_text())
        self.assertIsNone(contract['slot']);self.assertIsNone(contract['required_skill_settings'])
        config=(ROOT/'packaging/robotd-profile.toml').read_text()
        self.assertNotIn('roller_stand',config);self.assertIn('lb = "kick_left"',config)
    def test_no_new_browser_input_paths(self):
        import zipfile
        with zipfile.ZipFile(ROOT/'base/Microduck-Console-R17-V161.zip') as archive:
            prefix=archive.namelist()[0].split('/')[0]+'/'
            for name in ('controls.py','remote_input.py','static/control.js','static/webpad-controls.js'):
                self.assertEqual((ROOT/'console'/name).read_bytes(),archive.read(prefix+name))
if __name__=='__main__':unittest.main()
