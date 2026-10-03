"""Restore a verified publisher artifact verbatim. No collection or time rewriting."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import zipfile
from datetime import datetime

MAX_ZIP = 32 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024


def validate_run(run):
    if (run.get('path') != '.github/workflows/deploy-gh-pages.yml' or run.get('head_branch') != 'main'
            or run.get('status') != 'completed' or run.get('conclusion') != 'success'
            or not re.fullmatch(r'[a-f0-9]{40}', run.get('head_sha', ''))):
        raise ValueError('Restore only a completed successful main publisher run.')


def paired_snapshot(news, health):
    if (not isinstance(news, dict) or not isinstance(health, dict)
            or not isinstance(news.get('generated_at'), str)
            or health.get('checked_at') != news['generated_at']):
        return False
    try:
        datetime.fromisoformat(news['generated_at'].replace('Z', '+00:00'))
    except ValueError:
        return False
    if news.get('snapshot_id') is not None:
        return (isinstance(news['snapshot_id'], str) and bool(news['snapshot_id'])
                and health.get('snapshot_id') == news['snapshot_id'])
    return health.get('snapshot_id') is None


def unpack_pages(payload, output, workspace, baseline=None):
    output, workspace = output.resolve(), workspace.resolve()
    if not output.is_relative_to(workspace / 'artifacts') or output.exists():
        raise ValueError('Restore needs a new directory inside this workspace artifacts directory.')
    if len(payload) > MAX_ZIP:
        raise ValueError('Pages archive exceeds its compressed bound.')
    if baseline is not None and hashlib.sha256(payload).hexdigest() != baseline.get('archive_sha256'):
        raise ValueError('Frozen capsule archive checksum differs from its committed pin.')
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        entries = archive.infolist()
        if len(entries) != 1 or entries[0].filename != 'artifact.tar' or entries[0].file_size > MAX_EXPANDED:
            raise ValueError('Expected exactly one bounded Pages artifact.tar.')
        tar_payload = archive.read(entries[0])
    with tarfile.open(fileobj=io.BytesIO(tar_payload)) as archive:
        entries = archive.getmembers()
        if not entries or len(entries) > 512 or sum(entry.size for entry in entries) > MAX_EXPANDED:
            raise ValueError('Pages expansion exceeds its bounds.')
        names = set()
        for entry in entries:
            path = PurePosixPath(entry.name)
            name = str(path)
            if (path.is_absolute() or '..' in path.parts or '\\' in entry.name or ':' in entry.name
                    or not (entry.isfile() or entry.isdir()) or name in names):
                raise ValueError('Unsafe or duplicate Pages artifact path.')
            names.add(name)
        required = {'index.html', 'sw.js', 'data/news.json', 'data/source-health.json'}
        if not required <= names:
            raise ValueError('Pages artifact lacks its application or paired data.')
        output.mkdir(parents=True, exist_ok=False)
        archive.extractall(output, filter='data')
    news = json.loads((output / 'data/news.json').read_text(encoding='utf-8'))
    health = json.loads((output / 'data/source-health.json').read_text(encoding='utf-8'))
    if not news.get('generated_at') or not isinstance(news.get('articles'), list) or not 1 <= len(news['articles']) <= 2000:
        raise ValueError('Invalid paired news snapshot.')
    if not paired_snapshot(news, health):
        raise ValueError('Paired snapshot and report IDs or check timestamps differ.')
    release_path = output / 'release.json'
    release = json.loads(release_path.read_text(encoding='utf-8')) if release_path.exists() else None
    files = {path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(output.rglob('*')) if path.is_file()}
    report = {'schema_version': 1, 'archive_sha256': hashlib.sha256(payload).hexdigest(),
            'version': release.get('version') if release else news.get('meta', {}).get('version'),
            'generated_at': news['generated_at'], 'snapshot_id': news.get('snapshot_id'),
            'articles': len(news['articles']), 'file_sha256': files,
            'recollection_performed': False, 'timestamps_rewritten': False}
    if baseline is not None:
        for key in ('file_sha256', 'version', 'generated_at', 'snapshot_id', 'articles'):
            if report[key] != baseline.get(key):
                raise ValueError(f'Frozen baseline {key} differs from its original receipt.')
    return report


def api(repository, suffix):
    return json.loads(subprocess.check_output(['gh', 'api', f'repos/{repository}/{suffix}'], timeout=30))


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--run', type=int)
    source.add_argument('--baseline', help='Committed frozen release capsule name; never an arbitrary URL.')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.run is not None and args.run <= 0:
        raise ValueError('Invalid source run ID.')
    repository = os.environ.get('GITHUB_REPOSITORY', 'AureliusWu/News')
    if repository.casefold() != 'aureliuswu/news':
        raise ValueError('This restore is restricted to the News repository.')
    baseline = None
    if args.baseline:
        registry = json.loads(Path(__file__).with_name('rollback-baselines.json').read_text(encoding='utf-8'))
        baseline = registry.get(args.baseline)
        if not isinstance(baseline, dict):
            raise ValueError('Unknown frozen rollback capsule.')
    source_run_id = baseline['source_run_id'] if baseline else args.run
    run = api(repository, f'actions/runs/{source_run_id}')
    validate_run(run)
    if baseline:
        if run['head_sha'] != baseline['source_revision']:
            raise ValueError('Frozen capsule provenance differs from its original publisher run.')
        release = api(repository, f'releases/tags/{baseline["release_tag"]}')
        assets = [item for item in release['assets'] if item['name'] == baseline['asset_name']]
        if release.get('draft') or len(assets) != 1 or assets[0]['size'] > MAX_ZIP:
            raise ValueError('No unique bounded published frozen capsule.')
        payload = subprocess.check_output(['gh', 'api', '--header', 'Accept: application/octet-stream',
            f'repos/{repository}/releases/assets/{assets[0]["id"]}'], timeout=120)
        artifact_id = baseline['source_artifact_id']
    else:
        artifacts = api(repository, f'actions/runs/{source_run_id}/artifacts')['artifacts']
        pages = [item for item in artifacts if item['name'] == 'github-pages' and not item['expired']]
        if len(pages) != 1 or pages[0]['size_in_bytes'] > MAX_ZIP:
            raise ValueError('No unique unexpired bounded Pages artifact; never substitute recollected data.')
        payload = subprocess.check_output(['gh', 'api', f'repos/{repository}/actions/artifacts/{pages[0]["id"]}/zip'], timeout=120)
        artifact_id = pages[0]['id']
    workspace = Path(os.environ.get('GITHUB_WORKSPACE', Path.cwd())).resolve()
    report_path = args.report.resolve()
    if not report_path.is_relative_to(workspace / 'artifacts'):
        raise ValueError('Restore report must stay inside this workspace artifacts directory.')
    report = unpack_pages(payload, args.output, workspace, baseline)
    report.update(source_run_id=source_run_id, source_revision=run['head_sha'], source_artifact_id=artifact_id)
    if baseline:
        report.update(frozen_capsule=args.baseline, release_asset_id=assets[0]['id'],
            original_archive_sha256=baseline['original_archive_sha256'], capsule_repacked=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'file_sha256'}))


if __name__ == '__main__':
    main()
