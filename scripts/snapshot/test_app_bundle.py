import hashlib
import io
from pathlib import Path
import tempfile
import unittest
import zipfile
from app_bundle import unpack


def archive(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, body in files.items(): z.writestr(name, body)
    return stream.getvalue()


class BundleTests(unittest.TestCase):
    def test_restores_verified_code_without_replacing_data(self):
        payload = archive({'index.html': '<html lang="zh-CN">', 'sw.js': 'service worker', 'assets/a.js': 'app code'})
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory); (target / 'data').mkdir(); (target / 'data/news.json').write_text('keep')
            unpack(payload, target, hashlib.sha256(payload).hexdigest())
            self.assertEqual((target / 'assets/a.js').read_text(), 'app code')
            self.assertEqual((target / 'data/news.json').read_text(), 'keep')

    def test_rejects_invalid_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError): unpack(b'bad', Path(directory), 'a' * 64)

    def test_rejects_traversal_and_data_in_archive(self):
        for name in ('../escape', '/absolute', 'data/news.json', 'C:\\escape'):
            payload = archive({'index.html': 'app', 'sw.js': 'sw', name: 'unsafe'})
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError): unpack(payload, Path(directory), hashlib.sha256(payload).hexdigest())


if __name__ == '__main__': unittest.main()
