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

MAX_ZIP = 32 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024


def validate_run(run):
    if (run.get('path') != '.github/workflows/deploy-gh-pages.yml' or run.get('head_branch') != 'main'
            or run.get('status') != 'completed' or run.get('conclusion') != 'success'
            or not re.fullmatch(r'[a-f0-9]{40}', run.get('head_sha', ''))):
        raise ValueError('Restore only a completed successful main publisher run.')


def unpack_pages(payload, output, workspace):
    output, workspace = output.resolve(), workspace.resolve()
    if not output.is_relative_to(workspace / 'artifacts') or output.exists():
        raise ValueError('Restore needs a new directory inside this workspace artifacts directory.')
    if len(payload) > MAX_ZIP:
        raise ValueError('Pages archive exceeds its compressed bound.')
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
    if news.get('snapshot_id'):
        if any(health.get(key) != news.get(key) for key in ('snapshot_id', 'generated_at', 'content_sha256')):
            raise ValueError('Paired snapshot and report generations differ.')
    elif health.get('checked_at') != news['generated_at']:
        raise ValueError('Legacy paired report timestamp differs.')
    release_path = output / 'release.json'
    release = json.loads(release_path.read_text(encoding='utf-8')) if release_path.exists() else None
    files = {path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(output.rglob('*')) if path.is_file()}
    return {'schema_version': 1, 'archive_sha256': hashlib.sha256(payload).hexdigest(),
            'version': release.get('version') if release else news.get('meta', {}).get('version'),
            'generated_at': news['generated_at'], 'snapshot_id': news.get('snapshot_id'),
            'articles': len(news['articles']), 'file_sha256': files,
            'recollection_performed': False, 'timestamps_rewritten': False}


def api(repository, suffix):
    return json.loads(subprocess.check_output(['gh', 'api', f'repos/{repository}/{suffix}'], timeout=30))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.run <= 0:
        raise ValueError('Invalid source run ID.')
    repository = os.environ.get('GITHUB_REPOSITORY', 'AureliusWu/News')
    if repository.casefold() != 'aureliuswu/news':
        raise ValueError('This restore is restricted to the News repository.')
    run = api(repository, f'actions/runs/{args.run}')
    validate_run(run)
    artifacts = api(repository, f'actions/runs/{args.run}/artifacts')['artifacts']
    pages = [item for item in artifacts if item['name'] == 'github-pages' and not item['expired']]
    if len(pages) != 1 or pages[0]['size_in_bytes'] > MAX_ZIP:
        raise ValueError('No unique unexpired bounded Pages artifact; never substitute recollected data.')
    payload = subprocess.check_output(['gh', 'api', f'repos/{repository}/actions/artifacts/{pages[0]["id"]}/zip'], timeout=120)
    workspace = Path(os.environ.get('GITHUB_WORKSPACE', Path.cwd())).resolve()
    report_path = args.report.resolve()
    if not report_path.is_relative_to(workspace / 'artifacts'):
        raise ValueError('Restore report must stay inside this workspace artifacts directory.')
    report = unpack_pages(payload, args.output, workspace)
    report.update(source_run_id=args.run, source_revision=run['head_sha'], source_artifact_id=pages[0]['id'])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'file_sha256'}))


if __name__ == '__main__':
    main()
