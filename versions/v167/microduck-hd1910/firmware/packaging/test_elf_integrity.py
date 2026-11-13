"""Check file ranges without executing or loading ARM binaries."""
import hashlib
from pathlib import Path
import shutil
import struct
import tempfile
import unittest

from elf_integrity import NATIVE_FILES, validate_bundle, validate_elf

HERE = Path(__file__).resolve().parent
FULL_ORT_HASH = 'f1ec1a08eb99bd6e5401340f0a2b101381bf4694415480291dc13bcaa30f9ec7'


def sample_elf():
    data = bytearray(512)
    ident = b'\x7fELF\x02\x01\x01' + bytes(9)
    struct.pack_into('<16sHHIQQQIHHHHHH', data, 0,
                     ident, 3, 183, 1, 0, 64, 384, 0, 64, 56, 1, 64, 2, 0)
    struct.pack_into('<IIQQQQQQ', data, 64, 1, 5, 0, 0, 0, 512, 512, 4096)
    struct.pack_into('<IIQQQQIIQQ', data, 448, 0, 1, 0, 0, 256, 32, 0, 0, 1, 0)
    return data


class ElfIntegrityTests(unittest.TestCase):
    def check_data(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'native'
            path.write_bytes(data)
            return validate_elf(path)

    def full_ort(self):
        # The frozen baseline is preferred while auditing a local release.
        # The same complete library is shipped beside this portable test.
        baseline = HERE.parents[1] / 'Microduck-Source-R17-v1.0.150/packaging/onnxruntime/libonnxruntime.so.1.28.0'
        return baseline if baseline.is_file() else HERE / 'onnxruntime/libonnxruntime.so.1.28.0'

    def test_actual_full_baseline_ort_passes(self):
        path = self.full_ort()
        self.assertEqual(path.stat().st_size, 20_591_712)
        with path.open('rb') as stream:
            self.assertEqual(hashlib.file_digest(stream, 'sha256').hexdigest(), FULL_ORT_HASH)
        self.assertEqual(validate_elf(path)['machine'], 'AArch64')

    def test_actual_v152_truncated_ort_is_rejected(self):
        broken = HERE.parents[1] / 'Microduck-Source-R17-v1.0.152/packaging/onnxruntime/libonnxruntime.so.1.28.0'
        if broken.is_file() and broken.stat().st_size == 14_073_856:
            with self.assertRaisesRegex(ValueError, 'exceeds file size'):
                validate_elf(broken)
        else:
            # Preserve the exact truncation reported by v152 even when the old
            # release directory is unavailable in another checkout.
            with tempfile.TemporaryDirectory() as tmp:
                broken = Path(tmp) / 'libonnxruntime.so.1.28.0'
                shutil.copy2(self.full_ort(), broken)
                with broken.open('r+b') as stream:
                    stream.truncate(14_073_856)
                with self.assertRaisesRegex(ValueError, 'exceeds file size'):
                    validate_elf(broken)

    def test_truncated_header_and_program_table_fail(self):
        with self.assertRaisesRegex(ValueError, 'ELF header'):
            self.check_data(bytes(32))
        data = sample_elf()
        struct.pack_into('<Q', data, 32, 490)
        with self.assertRaisesRegex(ValueError, 'program table'):
            self.check_data(data)

    def test_section_table_and_section_file_range_fail(self):
        data = sample_elf()
        struct.pack_into('<Q', data, 40, 480)
        with self.assertRaisesRegex(ValueError, 'section table'):
            self.check_data(data)
        data = sample_elf()
        struct.pack_into('<Q', data, 448 + 24, 500)
        with self.assertRaisesRegex(ValueError, 'section 1'):
            self.check_data(data)

    def test_nobits_section_has_no_file_contents(self):
        data = sample_elf()
        struct.pack_into('<I', data, 448 + 4, 8)
        struct.pack_into('<QQ', data, 448 + 24, 800, 4096)
        self.assertEqual(self.check_data(data)['load_segments'], 1)

    def test_wrong_architecture_and_invalid_load_sizes_fail(self):
        data = sample_elf()
        struct.pack_into('<H', data, 18, 62)
        with self.assertRaisesRegex(ValueError, 'AArch64'):
            self.check_data(data)
        data = sample_elf()
        struct.pack_into('<Q', data, 64 + 40, 511)
        with self.assertRaisesRegex(ValueError, 'memory size'):
            self.check_data(data)

    def test_bundle_requires_all_seven_native_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in NATIVE_FILES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(sample_elf())
            self.assertEqual(set(validate_bundle(root)), set(NATIVE_FILES))
            (root / NATIVE_FILES[-1]).unlink()
            with self.assertRaisesRegex(ValueError, 'missing or invalid'):
                validate_bundle(root)


if __name__ == '__main__':
    unittest.main()
