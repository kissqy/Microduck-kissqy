import json, socket, sys, threading, unittest
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from connection_retry import ConnectionRetry, RetryStopped
from controls import Transport
from service_channel import ServiceChannel
import raw_telemetry as raw
class RetryTests(unittest.TestCase):
    def test_fixed_delay_three_retries_and_flapping_does_not_reset_budget(self):
        now=[0];retry=ConnectionRetry(lambda:now[0])
        for i in range(4):
            retry.check();retry.connected();now[0]+=.2;retry.failed()
            self.assertEqual(retry.remaining(),10)
            with self.assertRaises(RetryStopped):retry.check()
            now[0]+=10
        self.assertTrue(retry.exhausted)
        with self.assertRaises(RetryStopped):retry.check()

    def test_stable_connection_gets_a_new_failure_budget(self):
        now=[0];retry=ConnectionRetry(lambda:now[0])
        retry.failed();now[0]=10;retry.connected();now[0]=40;retry.failed()
        self.assertEqual(retry.failures,1)

    def test_web_input_retries_are_bounded_on_backend_even_if_pages_keep_requesting(self):
        now=[0];client=Transport('duck');client.input_retry=ConnectionRetry(lambda:now[0])
        def channel(*a,**kw):
            obj=Mock(error=None);obj.start.side_effect=OSError('input login refused');return obj
        with patch('controls.InputChannel',side_effect=channel) as create:
            for i in range(4):
                now[0]=i*10
                with self.assertRaises(OSError):client.call({'action':'connect'})
                with self.assertRaises(RetryStopped):client.call({'action':'connect'})
                self.assertEqual(create.call_count,i+1)
            now[0]=10000
            with self.assertRaises(RetryStopped):client.call({'action':'connect'})
            self.assertEqual(create.call_count,4)
        client.close()

    def test_management_queries_cannot_start_unlimited_logins(self):
        now=[0];channel=ServiceChannel('duck','/run/robotd.sock');channel.retry=ConnectionRetry(lambda:now[0])
        with patch('service_channel.spawn_process',side_effect=OSError('ssh unavailable')) as spawn:
            for i in range(4):
                now[0]=i*10
                with self.assertRaises(OSError):channel.request({'kind':'manage','argv':['true']},1)
                with self.assertRaises(RetryStopped):channel.request({'kind':'manage','argv':['true']},1)
            now[0]=10000
            with self.assertRaises(RetryStopped):channel.request({'kind':'manage','argv':['true']},1)
            self.assertEqual(spawn.call_count,4)
        channel.close()

class FastStop(threading.Event):
    def __init__(self):super().__init__();self.delays=[]
    def wait(self, timeout=None):
        if timeout==10:self.delays.append(timeout);return super().wait(.01)
        return super().wait(timeout)

class CollectorRetryTests(unittest.TestCase):
    def config(self):return {'hub':raw.Hub(),'robotd_socket':'/run/robotd.sock','tofd_socket':'/run/tofd/tof.sock'}
    def test_both_independent_channels_stop_after_four_failed_connections(self):
        stop=FastStop();events=[];calls=Counter();config=self.config()
        def fail(target,path,*a,**k):calls[path]+=1;raise OSError('fixture link unavailable')
        with patch('socket_transport.open_remote_socket',side_effect=fail):
            raw.raw_loop('duck',config,events.append,stop)
        self.assertEqual(calls,{'/run/robotd.sock':4,'/run/tofd/tof.sock':4})
        self.assertEqual(stop.delays,[10]*6)
        self.assertTrue(any(e.get('channel')=='state' and '已停止' in e.get('error','') for e in events))
        self.assertTrue(any(e.get('channel')=='tof' and '已停止' in e.get('error','') for e in events))

    def test_tof_exhaustion_keeps_healthy_robot_subscription(self):
        stop=FastStop();events=[];calls=Counter();config=self.config();ready=threading.Event();exhausted=threading.Event()
        peers=[];servers=[];requests=[]
        @contextmanager
        def opened(target,path,*a,**k):
            calls[path]+=1
            if path==config['tofd_socket']:raise OSError('fixture ToF offline')
            client,server=socket.socketpair();peers.extend((client,server))
            def serve():
                try:
                    line=b''
                    while not line.endswith(b'\n'):
                        part=server.recv(1)
                        if not part:return
                        line+=part
                    request=json.loads(line);requests.append(request['method'])
                    if request['method']=='robot.startupSubscribe':
                        server.sendall((json.dumps({'id':1,'result':{'steps':{str(n):{'status':'success','detail':'ready'} for n in range(1,5)}}})+'\n').encode())
                    else:
                        server.sendall(b'{"id":1,"result":{"accepted":true,"schema":"r17.raw.v1","framing":"u32le"}}\n');ready.set()
                    stop.wait(2)
                except OSError:pass
                finally:server.close()
            worker=threading.Thread(target=serve,daemon=True);servers.append(worker);worker.start()
            try:yield client
            finally:client.close()
        class Log:
            def add(self,source,text):
                if source=='ToF 数据连接' and '已停止' in text:exhausted.set()
        with patch('socket_transport.open_remote_socket',side_effect=opened):
            worker=threading.Thread(target=raw.raw_loop,args=('duck',config,events.append,stop,Log()),daemon=True);worker.start()
            try:
                self.assertTrue(ready.wait(1));self.assertTrue(exhausted.wait(1))
                self.assertTrue(worker.is_alive());self.assertEqual(calls[config['tofd_socket']],4)
                self.assertEqual(requests.count('robot.rawSubscribe'),1)
                self.assertFalse(any(e.get('channel')=='state' and 'error' in e for e in events))
            finally:
                stop.set();worker.join(2)
                for peer in peers:peer.close()
                for server in servers:server.join(1)
            self.assertFalse(worker.is_alive())

    def test_deliberate_pause_or_stop_does_not_spend_failure_budget(self):
        stop=FastStop();pause=threading.Event();events=[];log=Mock()
        def close_for_pause(*a,**k):pause.set();stop.set();raise OSError('planned close')
        with patch('socket_transport.open_remote_socket',side_effect=close_for_pause):
            raw.raw_loop('duck',self.config(),events.append,stop,log,pause)
        self.assertEqual(stop.delays,[])
        self.assertFalse(any('error' in e for e in events));log.add.assert_not_called()

if __name__=='__main__':unittest.main()
