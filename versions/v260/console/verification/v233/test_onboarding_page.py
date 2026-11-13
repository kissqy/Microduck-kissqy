"""Real form-handler boundaries and embedded offline photo, without network changes."""
import base64
from email.message import Message
import hashlib
from html.parser import HTMLParser
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from urllib.parse import urlencode

PC=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PC/'verification/v230'))
from test_support import FW
sys.path.insert(0,str(FW/'system-repair'))


def portal():
    source=(FW/'system-repair/microduck-public-image.sh').read_text().split('#__PORTAL_BEGIN__\n',1)[1].split('#__PORTAL_END__',1)[0]
    scope={'__name__':'v233_onboarding_fixture'}
    exec(compile(source,'v233-portal','exec'),scope)
    return scope


class Fields(HTMLParser):
    def __init__(self):
        super().__init__();self.inputs={};self.images=[]
    def handle_starttag(self,tag,attrs):
        data=dict(attrs)
        if tag=='input':self.inputs[data.get('name')]=data
        if tag=='img':self.images.append(data)


class OnboardingPageTests(unittest.TestCase):
    def submit(self,system_password,wifi_password='fixture-wifi-password'):
        env=portal();requests=[];responses=[]
        class Thread:
            def __init__(self,**kwargs):self.kwargs=kwargs
            def start(self):requests.append(self.kwargs)
        env['threading']=SimpleNamespace(Thread=Thread)
        handler=object.__new__(env['Handler'])
        handler.path='/connect';handler.server=object()
        handler.headers=Message();handler.headers['Content-Type']='application/x-www-form-urlencoded'
        body=urlencode({'token':env['TOKEN'],'ssid':'fixture-wifi','password':wifi_password,
                        'system_password':system_password}).encode()
        handler.headers['Content-Length']=str(len(body));handler.rfile=io.BytesIO(body)
        handler.send_html=lambda content,status=200:responses.append((status,content))
        handler.do_POST()
        return requests,responses

    def test_six_character_system_password_starts_the_original_provision_worker(self):
        requests,responses=self.submit('abc123')
        self.assertEqual(responses[0][0],200)
        self.assertEqual(len(requests),1)
        self.assertEqual(requests[0]['args'][2],'abc123')

    def test_short_long_and_control_character_system_passwords_are_rejected(self):
        for password in ('abc12','x'*129,'abc\n12'):
            with self.subTest(length=len(password)):
                requests,responses=self.submit(password)
                self.assertEqual(responses[0][0],400)
                self.assertEqual(requests,[])

    def test_wifi_passphrase_still_requires_eight_characters(self):
        requests,responses=self.submit('abc123',wifi_password='1234567')
        self.assertEqual(responses[0][0],400)
        self.assertEqual(requests,[])

    def test_html_brand_photo_and_password_fields_match_the_handler(self):
        env=portal();handler=object.__new__(env['Handler'])
        page=handler.page();fields=Fields();fields.feed(page)
        self.assertIn('<title>kissqy · Microduck 重新配网</title>',page)
        self.assertIn('<h1>连接你的 <span>kissqy 小鸭</span></h1>',page)
        self.assertEqual(fields.inputs['system_password']['minlength'],'6')
        self.assertEqual(fields.inputs['system_password']['maxlength'],'128')
        self.assertEqual(fields.inputs['password']['minlength'],'8')
        self.assertEqual(fields.images[0]['src'],'/mascot.webp')
        self.assertEqual((fields.images[0]['width'],fields.images[0]['height']),('1040','585'))
        self.assertIn('kissqy 开源仓库 · 一键系统 · 轻松配网',page)

    def test_photo_route_serves_the_user_selected_four_duck_artwork_offline(self):
        env=portal();raw=env['MASCOT_WEBP']
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         '15285ab6824ef7695dc66a16454fb24cde1b7437f2330cb6cb7c882bb8b91822')
        handler=object.__new__(env['Handler']);handler.wfile=io.BytesIO();headers={}
        handler.send_response=lambda status:self.assertEqual(status,200)
        handler.send_header=lambda key,value:headers.__setitem__(key,value)
        handler.end_headers=lambda:None
        handler.send_mascot()
        self.assertEqual(headers['Content-Type'],'image/webp')
        self.assertEqual(handler.wfile.getvalue(),raw)


if __name__=='__main__':unittest.main()
