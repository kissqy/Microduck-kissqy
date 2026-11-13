import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from system_log import SystemLog,describe

class LogTests(unittest.TestCase):
    def test_repeated_transport_failure_keeps_first_reason_count_last_time_and_new_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            log=SystemLog(directory);log.hide('secret-key')
            for _ in range(100):log.add('原始遥测','Permission denied secret-key')
            log.add('原始遥测','Connection reset')
            for _ in range(2):log.add('服务操作','用户请求回 HOME')
            data=log.download().decode();log.close()
            self.assertIn('另重复 99 次',data);self.assertIn('最后发生',data)
            self.assertIn('Connection reset',data);self.assertNotIn('secret-key',data)
            self.assertEqual(data.count('用户请求回 HOME'),2)

    def test_rotation_keeps_startup_context_recent_failure_and_reports_removed_history(self):
        with tempfile.TemporaryDirectory() as directory:
            log=SystemLog(directory,max_bytes=4096)
            log.add('中控启动','V173 / control.48')
            for i in range(400):log.add('操作',f'event {i}: '+'x'*150)
            log.add('服务操作错误','LAST: missing IMU 200')
            data=log.download().decode();log.close()
            self.assertIn('V173 / control.48',data);self.assertIn('LAST: missing IMU 200',data)
            self.assertIn('更早的中间记录已移除',data)
            self.assertNotIn('event 250:',data)
            self.assertLess(len(data.encode()),2*4096+65536+4096)
            self.assertEqual(len(list(Path(directory).glob('*.log'))),2)

    def test_inline_scripts_and_huge_single_entries_are_not_exported_in_full(self):
        self.assertEqual(describe({'kind':'manage','argv':['python3','-u','-c','secret source','--option']}),"python3 -u -c '[内置脚本]' --option")
        with tempfile.TemporaryDirectory() as directory:
            log=SystemLog(directory)
            log.add('SSH 输出','BEGIN:'+'x'*100000+':END: error 5')
            data=log.download().decode();log.close()
            self.assertLess(len(data),17000);self.assertIn('BEGIN:',data);self.assertIn('END: error 5',data)
            self.assertIn('过长单条输出',data)

if __name__=='__main__':unittest.main()
