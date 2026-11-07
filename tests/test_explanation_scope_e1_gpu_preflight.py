"""Mock GPU preflight logic without querying or initializing any real GPU."""
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import verify_explanation_scope_e1_gpu as preflight


class GPUPreflightTests(unittest.TestCase):
    def sample(self, processes=''):
        return [SimpleNamespace(stdout='0, GPU-test-uuid, Fake GPU, 24000, 100, 555.00\n'),
                SimpleNamespace(stdout=processes)]

    def test_busy_gpu_never_imports_or_initializes_torch_cuda(self):
        fake = SimpleNamespace(cuda=MagicMock())
        with patch.object(preflight.subprocess, 'run', side_effect=self.sample('123, trainer, 2048\n')), \
             patch.dict(sys.modules, {'torch': fake}):
            result = preflight.inspect(0)
        self.assertEqual(result['status'], 'busy_cuda_not_initialized')
        self.assertFalse(result['pytorch_cuda_checked'])
        fake.cuda.is_available.assert_not_called()
        self.assertFalse(result['collection_allowed'])

    def test_available_device_is_observed_but_never_declared_ready(self):
        cuda = MagicMock()
        cuda.is_available.return_value = True
        cuda.device_count.return_value = 1
        cuda.get_device_name.return_value = 'Fake GPU'
        cuda.is_bf16_supported.return_value = True
        fake = SimpleNamespace(cuda=cuda, __version__='fake', version=SimpleNamespace(cuda='12.fake'))
        with patch.object(preflight.subprocess, 'run', side_effect=self.sample()), \
             patch.dict(sys.modules, {'torch': fake}), patch.dict(preflight.os.environ, {}, clear=False):
            result = preflight.inspect(0)
            self.assertEqual(preflight.os.environ['CUDA_VISIBLE_DEVICES'], 'GPU-test-uuid')
        self.assertTrue(result['bf16_supported'])
        self.assertFalse(result['gpu_launch_ready'])
        self.assertFalse(result['model_inference'])

    def test_missing_cuda_and_invalid_gpu_respect_closed_gate(self):
        cuda = MagicMock()
        cuda.is_available.return_value = False
        fake = SimpleNamespace(cuda=cuda, __version__='fake', version=SimpleNamespace(cuda=None))
        with patch.object(preflight.subprocess, 'run', side_effect=self.sample()), \
             patch.dict(sys.modules, {'torch': fake}), patch.dict(preflight.os.environ, {}, clear=False):
            result = preflight.inspect(0)
        self.assertFalse(result['cuda_available'])
        self.assertIsNone(result['bf16_supported'])
        cuda.is_bf16_supported.assert_not_called()
        with self.assertRaises(ValueError):
            preflight.inspect(-1)

    def test_nvidia_smi_failure_does_not_run_cuda(self):
        fake = SimpleNamespace(cuda=MagicMock())
        with patch.object(preflight.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'nvidia-smi')), \
             patch.dict(sys.modules, {'torch': fake}):
            with self.assertRaises(subprocess.CalledProcessError):
                preflight.inspect(0)
        fake.cuda.is_available.assert_not_called()


if __name__ == '__main__':
    unittest.main()
