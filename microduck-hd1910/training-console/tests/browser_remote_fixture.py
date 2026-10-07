import sys
from pathlib import Path
import tempfile
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import training_console as c
from training.remote_ssh import RemoteTraining
with tempfile.TemporaryDirectory() as directory:
 manager=c.TrainingManager(directory=Path(directory))
 manager.remote=RemoteTraining(manager.directory,c.ROOT,manager,c.save_json)
 def fail_connect(operation):
  with manager.remote.lock:
   manager.remote.status='failed';manager.remote.message='测试连接失败，未启动本机训练。';manager.remote.operation=None
 manager.remote._connect=fail_connect
 server=ThreadingHTTPServer(('127.0.0.1',0),c.handler_for(manager,'remote-browser-token'))
 print('FIXTURE_READY',server.server_port,flush=True)
 try:server.serve_forever()
 finally:server.server_close();manager.remote.close();manager.close()
