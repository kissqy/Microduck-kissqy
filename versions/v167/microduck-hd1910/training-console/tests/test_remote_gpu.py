"""SSH GPU telemetry must recognize WSL without claiming CUDA is unavailable."""
import subprocess
import unittest
from unittest.mock import Mock,patch
from training.remote_server_boot import gpu_summary

class RemoteGPU(unittest.TestCase):
    def test_noninteractive_wsl_uses_absolute_tool_path(self):
        with patch('training.remote_server_boot.shutil.which',return_value=None),patch('training.remote_server_boot.Path.is_file',return_value=True),patch('training.remote_server_boot.subprocess.run',return_value=Mock(returncode=0,stdout=b'RTX 4080 SUPER, 16376 MiB, 572.00\n')) as run:
            self.assertIn('4080 SUPER',gpu_summary())
            self.assertEqual(run.call_args.args[0][0],'/usr/lib/wsl/lib/nvidia-smi')
    def test_regular_linux_uses_discovered_path(self):
        with patch('training.remote_server_boot.shutil.which',return_value='/usr/bin/nvidia-smi'),patch('training.remote_server_boot.subprocess.run',return_value=Mock(returncode=0,stdout=b'NVIDIA A10, 23028 MiB, 572.00')) as run:
            self.assertIn('A10',gpu_summary());self.assertEqual(run.call_args.args[0][0],'/usr/bin/nvidia-smi')
    def test_missing_tool_does_not_claim_missing_driver_or_cuda(self):
        with patch('training.remote_server_boot.shutil.which',return_value=None),patch('training.remote_server_boot.Path.is_file',return_value=False),patch('training.remote_server_boot.subprocess.run') as run:
            message=gpu_summary();run.assert_not_called()
        self.assertIn('不代表CUDA不可用',message);self.assertNotIn('安装驱动',message)
    def test_timeout_is_not_reported_as_missing_tool(self):
        with patch('training.remote_server_boot.shutil.which',return_value='nvidia-smi'),patch('training.remote_server_boot.subprocess.run',side_effect=subprocess.TimeoutExpired('nvidia-smi',12)):
            self.assertIn('超时',gpu_summary());self.assertNotIn('未找到',gpu_summary())
    def test_failed_or_empty_result_does_not_claim_success(self):
        for result in (Mock(returncode=1,stdout=b''),Mock(returncode=0,stdout=b'\n')):
            with patch('training.remote_server_boot.shutil.which',return_value='nvidia-smi'),patch('training.remote_server_boot.subprocess.run',return_value=result):
                self.assertIn('未返回有效数据',gpu_summary())

if __name__=='__main__':unittest.main()
