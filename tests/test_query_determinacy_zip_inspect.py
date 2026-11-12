import hashlib
import importlib.util
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/query_determinacy_zip_inspect.py'
SPEC = importlib.util.spec_from_file_location('query_zip_inspect', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ZipInspectionTests(unittest.TestCase):
    def test_inventory_hashes_without_extracting(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'pilot.zip'
            with zipfile.ZipFile(archive, 'w') as file:
                file.writestr('文件/README.md', '说明')
                file.writestr('文件/questions.csv', 'id,question\n')
            result = MODULE.inspect_archive(archive)
            self.assertEqual(result['archive_sha256'], hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertEqual(result['file_count'], 2)
            self.assertEqual(result['members'][0]['sha256'], hashlib.sha256('说明'.encode()).hexdigest())
            self.assertFalse(result['extracted'])
            self.assertFalse((Path(tmp) / '文件').exists())
            self.assertFalse(result['content_or_semantics_verified'])

    def test_rejects_unsafe_paths(self):
        for name in ('../outside', '/absolute', 'a/../../outside', 'C:/outside', 'a\\outside'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                archive = Path(tmp) / 'pilot.zip'
                with zipfile.ZipFile(archive, 'w') as file:
                    file.writestr(name, 'x')
                with self.assertRaisesRegex(ValueError, 'unsafe'):
                    MODULE.inspect_archive(archive)

    def test_rejects_duplicate_and_unicode_equivalent_paths(self):
        for names in (('same', 'same'), ('é', 'e\u0301')):
            with self.subTest(names=names), tempfile.TemporaryDirectory() as tmp:
                archive = Path(tmp) / 'pilot.zip'
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', UserWarning)
                    with zipfile.ZipFile(archive, 'w') as file:
                        for name in names:
                            file.writestr(name, 'x')
                with self.assertRaisesRegex(ValueError, 'duplicate'):
                    MODULE.inspect_archive(archive)

    def test_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'pilot.zip'
            link = zipfile.ZipInfo('link')
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(archive, 'w') as file:
                file.writestr(link, 'target')
            with self.assertRaisesRegex(ValueError, 'symbolic link'):
                MODULE.inspect_archive(archive)

    def test_rejects_oversized_member_before_reading(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'pilot.zip'
            with zipfile.ZipFile(archive, 'w') as file:
                file.writestr('large', '12345')
            original = MODULE.MAX_MEMBER_BYTES
            MODULE.MAX_MEMBER_BYTES = 4
            try:
                with self.assertRaisesRegex(ValueError, 'size limit'):
                    MODULE.inspect_archive(archive)
            finally:
                MODULE.MAX_MEMBER_BYTES = original


if __name__ == '__main__':
    unittest.main()
