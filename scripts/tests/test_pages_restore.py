import importlib.util
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('pages_restore', ROOT / 'scripts/restore-pages-artifact.py')
restore = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore)


def archive(extra=None):
    files = {'index.html': b'<html>synthetic</html>', 'sw.js': b'// synthetic',
             'data/news.json': json.dumps({'generated_at': '2026-10-01T00:00:00Z', 'articles': [{'id': 1}], 'meta': {'version': '0.2.0'}}).encode(),
             'data/source-health.json': b'{"checked_at":"2026-10-01T00:00:00Z"}'}
    if extra:
        files.update(extra)
    tar = io.BytesIO()
    with tarfile.open(fileobj=tar, mode='w') as output:
        for name, data in files.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            output.addfile(entry, io.BytesIO(data))
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, 'w') as output:
        output.writestr('artifact.tar', tar.getvalue())
    return payload.getvalue(), files


def current_archive(health=None):
    generated = '2026-10-03T00:00:00Z'
    news = {'generated_at': generated, 'snapshot_id': 'synthetic-current-id',
            'content_sha256': 'snapshot-only', 'articles': [{'id': 1}], 'meta': {'version': '0.4.0-alpha.1'}}
    if health is None:
        health = {'checked_at': generated, 'snapshot_id': news['snapshot_id']}
    return archive({'data/news.json': json.dumps(news).encode(),
                    'data/source-health.json': json.dumps(health).encode(),
                    'release.json': b'{"version":"0.9.0-alpha.1"}'})


class PagesRestoreTests(unittest.TestCase):
    def setUp(self):
        self.parent = (ROOT / 'artifacts/v1-m5-restore-unit-tests').resolve()
        self.parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=self.parent)
        self.workspace = Path(self.temporary.name).resolve()
        self.output = self.workspace / 'artifacts/site'

    def tearDown(self):
        # Verify the exact absolute cleanup target before tempfile recursively deletes it.
        self.assertTrue(self.workspace.is_relative_to(self.parent))
        self.temporary.cleanup()

    def test_pair_restored_verbatim_without_recollection(self):
        payload, files = archive()
        report = restore.unpack_pages(payload, self.output, self.workspace)
        self.assertEqual(report['generated_at'], '2026-10-01T00:00:00Z')
        self.assertFalse(report['timestamps_rewritten'])
        self.assertFalse(report['recollection_performed'])
        for name, data in files.items():
            self.assertEqual((self.output / name).read_bytes(), data)

    def test_unsafe_paths_rejected_before_extraction(self):
        for path in ('../outside', '/absolute', 'a\\b', 'C:/outside'):
            with self.subTest(path=path):
                payload, _ = archive({path: b'synthetic'})
                with self.assertRaises(ValueError):
                    restore.unpack_pages(payload, self.output, self.workspace)
                self.assertFalse(self.output.exists())

    def test_foreign_output_rejected(self):
        payload, _ = archive()
        with self.assertRaises(ValueError):
            restore.unpack_pages(payload, self.workspace / 'foreign', self.workspace)

    def test_existing_output_not_overwritten(self):
        payload, _ = archive()
        self.output.mkdir(parents=True)
        marker = self.output / 'keep'
        marker.write_text('preserve')
        with self.assertRaises(ValueError):
            restore.unpack_pages(payload, self.output, self.workspace)
        self.assertEqual(marker.read_text(), 'preserve')

    def test_cross_generation_data_rejected(self):
        payload, _ = archive({'data/source-health.json': b'{"checked_at":"2026-10-02T00:00:00Z"}'})
        with self.assertRaises(ValueError):
            restore.unpack_pages(payload, self.output, self.workspace)

    def test_only_successful_main_publisher_allowed(self):
        run = {'path': '.github/workflows/deploy-gh-pages.yml', 'head_branch': 'main',
               'status': 'completed', 'conclusion': 'success', 'head_sha': 'a' * 40}
        restore.validate_run(run)
        for key, value in [('head_branch', 'untrusted'), ('conclusion', 'failure'), ('path', '.github/workflows/other.yml')]:
            with self.assertRaises(ValueError):
                restore.validate_run({**run, key: value})

    def test_current_pair_restored_verbatim_without_snapshot_only_report_fields(self):
        payload, files = current_archive()
        report = restore.unpack_pages(payload, self.output, self.workspace)
        self.assertEqual(report['version'], '0.9.0-alpha.1')
        self.assertEqual(report['snapshot_id'], 'synthetic-current-id')
        for name, data in files.items():
            self.assertEqual((self.output / name).read_bytes(), data)

    def test_current_wrong_id_rejected(self):
        payload, _ = current_archive({'checked_at': '2026-10-03T00:00:00Z', 'snapshot_id': 'wrong'})
        with self.assertRaises(ValueError):
            restore.unpack_pages(payload, self.output, self.workspace)

    def test_current_wrong_check_timestamp_rejected(self):
        payload, _ = current_archive({'checked_at': '2026-10-02T00:00:00Z', 'snapshot_id': 'synthetic-current-id'})
        with self.assertRaises(ValueError):
            restore.unpack_pages(payload, self.output, self.workspace)

    def test_current_missing_id_rejected(self):
        payload, _ = current_archive({'checked_at': '2026-10-03T00:00:00Z'})
        with self.assertRaises(ValueError):
            restore.unpack_pages(payload, self.output, self.workspace)

    def test_current_missing_check_timestamp_rejected(self):
        payload, _ = current_archive({'generated_at': '2026-10-03T00:00:00Z', 'snapshot_id': 'synthetic-current-id'})
        with self.assertRaises(ValueError):
            restore.unpack_pages(payload, self.output, self.workspace)

    def test_malformed_and_cross_schema_pairs_fail_closed(self):
        for snapshot_id in ('', 0, {}, []):
            news = {'generated_at': '2026-10-03T00:00:00Z', 'snapshot_id': snapshot_id}
            self.assertFalse(restore.paired_snapshot(news, {'checked_at': news['generated_at'], 'snapshot_id': snapshot_id}))
        self.assertFalse(restore.paired_snapshot({'generated_at': 'invalid'}, {'checked_at': 'invalid'}))
        self.assertFalse(restore.paired_snapshot({'generated_at': '2026-10-03T00:00:00Z'},
                         {'checked_at': '2026-10-03T00:00:00Z', 'snapshot_id': 'unmatched'}))

    def frozen(self, payload, files):
        return {'archive_sha256': hashlib.sha256(payload).hexdigest(), 'version': '0.2.0',
                'generated_at': '2026-10-01T00:00:00Z', 'snapshot_id': None, 'articles': 1,
                'file_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}

    def test_frozen_capsule_restores_only_exact_original_files(self):
        payload, files = archive()
        pin = self.frozen(payload, files)
        report = restore.unpack_pages(payload, self.output, self.workspace, pin)
        self.assertEqual(report['file_sha256'], pin['file_sha256'])
        self.assertFalse(report['timestamps_rewritten'])

    def test_frozen_wrong_archive_rejected_before_extraction(self):
        payload, files = archive()
        pin = {**self.frozen(payload, files), 'archive_sha256': '0' * 64}
        with self.assertRaises(ValueError):
            restore.unpack_pages(payload, self.output, self.workspace, pin)
        self.assertFalse(self.output.exists())

    def test_frozen_changed_file_receipt_rejected(self):
        payload, files = archive()
        pin = self.frozen(payload, files)
        pin['file_sha256']['index.html'] = '0' * 64
        with self.assertRaises(ValueError):
            restore.unpack_pages(payload, self.output, self.workspace, pin)

    def test_frozen_changed_generation_rejected(self):
        payload, files = archive()
        pin = {**self.frozen(payload, files), 'generated_at': '2026-10-02T00:00:00Z'}
        with self.assertRaises(ValueError):
            restore.unpack_pages(payload, self.output, self.workspace, pin)


if __name__ == '__main__':
    unittest.main()
