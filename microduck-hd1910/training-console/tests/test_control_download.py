"""Transport regressions: no GPU, robot, or user's training files."""
import base64
import hashlib
import io
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import training_console as tc
from training.control_channel import ControlChannel
from training.sim_protocol import SimulationControls


class ControlDownloadTests(unittest.TestCase):
    def test_control_returns_while_transport_stalls_and_coalesces_to_release(self):
        entered, release = threading.Event(), threading.Event()
        messages = []
        class SlowPipe:
            def write(self, data):
                entered.set()
                release.wait(3)
                messages.append(json.loads(data))
            def flush(self): pass
        with tempfile.TemporaryDirectory() as directory:
            manager = tc.BaseTrainingManager(Path(directory))
            jid = 'a'*16
            manager.jobs[jid] = {'id':jid,'op':'play','status':'running','sim_controls':{'movement':True}}
            manager.processes[jid] = SimpleNamespace(stdin=SlowPipe(),poll=lambda:None)
            command = {'job_id':jid,'client':'browser_test','sequence':1,'action':'move','velocity':[.4,0,0]}
            try:
                started = time.monotonic()
                self.assertTrue(manager.control(command)['queued'])
                self.assertLess(time.monotonic()-started,.25)
                self.assertTrue(entered.wait(1))
                for seq in range(2,102): manager.control({**command,'sequence':seq})
                manager.control({**command,'sequence':102,'action':'zero'})
                channel = manager.control_channels[jid]
                self.assertEqual([m['action'] for m in channel.pending],['zero'])
                self.assertTrue(manager.control({**command,'sequence':101})['ignored'])
                release.set()
                deadline = time.monotonic()+1
                while len(messages)<2 and time.monotonic()<deadline: time.sleep(.005)
                self.assertEqual([m['action'] for m in messages],['move','zero'])
            finally:
                release.set()
                for channel in manager.control_channels.values(): channel.close()

    def test_expired_queue_and_out_of_order_moves_cannot_restart_movement(self):
        stream = io.BytesIO()
        channel = ControlChannel(SimpleNamespace(stdin=stream,poll=lambda:None),threading.Lock())
        try:
            channel.submit({'action':'move','expires_at':time.time()-1,'velocity':[.4,0,0]})
            channel.submit({'action':'zero','expires_at':time.time()+.7})
            deadline=time.monotonic()+1
            while not stream.getvalue() and time.monotonic()<deadline: time.sleep(.005)
            self.assertEqual([json.loads(m)['action'] for m in stream.getvalue().splitlines()],['zero'])
        finally: channel.close()
        control=SimulationControls(clock=lambda:10)
        control.receive({'action':'move','velocity':[.4,0,0],'expires_at':10.7,'client':'browser_test','sequence':1})
        control.receive({'action':'zero','client':'browser_test','sequence':3})
        control.receive({'action':'move','velocity':[.4,0,0],'expires_at':10.7,'client':'browser_test','sequence':2})
        self.assertEqual(control.sample(),(0,0,0))
        self.assertEqual(control.status()['sequence'],3)

    def test_pipe_failure_is_reported_without_silently_claiming_delivery(self):
        class BrokenPipe:
            def write(self,data): raise BrokenPipeError()
        channel=ControlChannel(SimpleNamespace(stdin=BrokenPipe(),poll=lambda:None),threading.Lock())
        channel.submit({'action':'zero'})
        channel.thread.join(timeout=1)
        with self.assertRaisesRegex(ValueError,'断开'):channel.submit({'action':'zero'})

    def test_download_uses_authenticated_json_without_attachment_and_exact_zip_bytes(self):
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('policy.onnx',b'fixture\x00\xff')
            archive.writestr('deployment-contract.json','{"scale":0.7}')
        data=output.getvalue()
        with tempfile.TemporaryDirectory() as directory:
            manager=tc.TrainingManager(Path(directory))
            server=tc.ThreadingHTTPServer(('127.0.0.1',0),tc.handler_for(manager,'fixture-token'))
            threading.Thread(target=server.serve_forever,daemon=True).start()
            url='http://127.0.0.1:'+str(server.server_port)+'/api/model/content'
            def request(token='fixture-token',jid='a'*16):
                return urllib.request.Request(url,data=json.dumps({'job_id':jid}).encode(),
                    headers={'Content-Type':'application/json','X-Training-Token':token})
            try:
                with patch.object(manager,'model_download',return_value=data) as download:
                    with urllib.request.urlopen(request()) as response:
                        self.assertIn('application/json',response.headers['Content-Type'])
                        self.assertIsNone(response.headers.get('Content-Disposition'))
                        payload=json.loads(response.read())
                    self.assertEqual(base64.b64decode(payload['data']),data)
                    self.assertEqual(payload['size'],len(data))
                    self.assertEqual(payload['sha256'],hashlib.sha256(data).hexdigest())
                    self.assertIsNone(zipfile.ZipFile(io.BytesIO(base64.b64decode(payload['data']))).testzip())
                    with self.assertRaises(urllib.error.HTTPError) as error: urllib.request.urlopen(request(token='wrong'))
                    self.assertEqual(error.exception.code,403)
                    with self.assertRaises(urllib.error.HTTPError) as error: urllib.request.urlopen(request(jid='../bad'))
                    self.assertEqual(error.exception.code,400)
                    download.assert_called_once_with('a'*16)
                with patch.object(manager,'model_download',return_value=b'{"error":"not zip"}'):
                    with self.assertRaises(urllib.error.HTTPError) as error: urllib.request.urlopen(request())
                    self.assertEqual(error.exception.code,400)
                    self.assertIsNone(error.exception.headers.get('Content-Disposition'))
            finally:
                server.shutdown();server.server_close()


if __name__=='__main__':unittest.main()
