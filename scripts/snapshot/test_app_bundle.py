import hashlib
import io
from pathlib import Path
import tempfile
import unittest
import zipfile
import json
from unittest.mock import patch
import httpx
from app_bundle import unpack, restore


def archive(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, body in files.items(): z.writestr(name, body)
    return stream.getvalue()


class BundleTests(unittest.TestCase):
    def test_formal_deployment_missing_archive_cannot_downgrade_to_candidate(self):
        response=httpx.Response(200,json={'formal_release':True},request=httpx.Request('GET','https://aureliuswu.github.io/News/release.json'))
        with patch('app_bundle.httpx.Client') as client:
            client.return_value.__enter__.return_value.get.return_value=response
            with self.assertRaises(ValueError): restore(Path('artifacts/unused-formal-test'))
    def test_pinned_data_refresh_never_falls_back_to_rebuilding_a_candidate(self):
        source = 'a' * 40
        for payload, status in (({'source_revision': 'b' * 40}, 200), ({'source_revision': source}, 200), ({}, 404)):
            response = httpx.Response(status, json=payload, request=httpx.Request('GET', 'https://aureliuswu.github.io/News/release.json'))
            with patch('app_bundle.httpx.Client') as client:
                mocked = client.return_value.__enter__.return_value
                mocked.get.return_value = response
                with self.assertRaises(ValueError): restore(Path('artifacts/unused-pinned-test'), source)
                self.assertEqual(mocked.get.call_count, 1)

    def test_pinned_data_refresh_preserves_formal_metadata(self):
        source = 'a' * 40
        payload = archive({'index.html': 'synthetic', 'sw.js': 'synthetic'})
        release = {'version': '1.1.0', 'source_revision': source, 'formal_release': True,
                   'app_bundle_sha256': hashlib.sha256(payload).hexdigest(), 'event_alias_schema_version': 1,
                   'event_matcher_version': 'title-summary-v4', 'data_schema_version': 1,
                   'base_path': '/News/', 'event_method_version': 'lexical-complete-link-v1'}
        parent = (Path(__file__).resolve().parents[2] / 'artifacts/v1.1-bundle-tests').resolve()
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        target = Path(temporary.name).resolve()
        try:
            with patch('app_bundle.httpx.Client') as client:
                client.return_value.__enter__.return_value.get.side_effect = [
                    httpx.Response(200, json=release, request=httpx.Request('GET', 'https://aureliuswu.github.io/News/release.json')),
                    httpx.Response(200, content=payload, request=httpx.Request('GET', 'https://aureliuswu.github.io/News/app-bundle.zip'))]
                self.assertTrue(restore(target, source))
            self.assertTrue(json.loads((target / 'release.json').read_text())['formal_release'])
            self.assertEqual((target / 'app-bundle.zip').read_bytes(), payload)
        finally:
            self.assertTrue(target.is_relative_to(parent))
            temporary.cleanup()
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
