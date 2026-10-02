"""Bounded, integrity-checked code bundles for data-only Pages refreshes."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import zipfile
import httpx

MAX_ARCHIVE = 2 * 1024 * 1024
MAX_EXPANDED = 4 * 1024 * 1024


def pack(directory, base):
    release_path = directory / 'release.json'
    release = json.loads(release_path.read_text(encoding='utf-8'))
    files = [p for p in sorted(directory.rglob('*')) if p.is_file() and 'data' not in p.relative_to(directory).parts
             and p.name not in ('release.json', 'app-bundle.zip')]
    if len(files) > 256 or sum(p.stat().st_size for p in files) > MAX_EXPANDED or any(p.is_symlink() for p in files):
        raise ValueError('Application bundle exceeds bounds or includes symbolic links.')
    archive = directory / 'app-bundle.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for file in files: z.write(file, file.relative_to(directory).as_posix())
    if archive.stat().st_size > MAX_ARCHIVE: raise ValueError('Application archive exceeds 2 MiB.')
    release.update(app_bundle_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), base_path=base,
                   event_method_version='lexical-complete-link-v1', event_matcher_version='title-summary-v4', event_alias_schema_version=1, asset_count=len(files))
    release_path.write_text(json.dumps(release, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'action': 'pack', 'version': release['version'], 'asset_count': len(files), 'bytes': archive.stat().st_size}))


def unpack(payload, directory, expected_digest):
    if len(payload) > MAX_ARCHIVE or not re.fullmatch('[a-f0-9]{64}', expected_digest) or hashlib.sha256(payload).hexdigest() != expected_digest:
        raise ValueError('Application archive digest or size is invalid.')
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        entries = archive.infolist()
        if not entries or len(entries) > 256 or sum(e.file_size for e in entries) > MAX_EXPANDED:
            raise ValueError('Application archive expansion exceeds bounds.')
        names = set()
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or ':' in entry.filename or entry.filename in names or 'data' in path.parts or entry.is_dir() or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Application archive contains an unsafe path.')
            names.add(entry.filename)
        if 'index.html' not in names or 'sw.js' not in names: raise ValueError('Application archive lacks its entry or service worker.')
        directory.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            target = directory.joinpath(*PurePosixPath(entry.filename).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(entry))


def restore(directory):
    base = 'https://aureliuswu.github.io/News/'
    with httpx.Client(timeout=25, follow_redirects=False) as client:
        response = client.get(base + 'release.json', headers={'Cache-Control': 'no-cache'})
        if response.status_code == 404: return False
        response.raise_for_status()
        if len(response.content) > 16384: raise ValueError('Application metadata exceeds its bound.')
        release = response.json()
        if not release.get('app_bundle_sha256'): return False
        if release.get('event_alias_schema_version') is None: return False
        if release.get('event_alias_schema_version') != 1 or release.get('event_matcher_version') != 'title-summary-v4':
            raise ValueError('Published code is incompatible with reviewed event aliases.')
        if release.get('data_schema_version') != 1 or release.get('base_path') != '/News/' or release.get('event_method_version') != 'lexical-complete-link-v1':
            raise ValueError('Published application is not compatible with current data rules.')
        response = client.get(base + 'app-bundle.zip')
        response.raise_for_status()
        unpack(response.content, directory, release['app_bundle_sha256'])
        (directory / 'app-bundle.zip').write_bytes(response.content)
        (directory / 'release.json').write_text(json.dumps(release, indent=2), encoding='utf-8')
        print(f'Restored verified application {release["version"]}; its code revision and build time are preserved.')
        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['pack', 'restore', 'overlay'])
    parser.add_argument('--directory', type=Path, default=Path('frontend/dist'))
    parser.add_argument('--base', default='/News/')
    args = parser.parse_args()
    if args.operation == 'pack': pack(args.directory, args.base)
    elif args.operation == 'overlay':
        shutil.copytree('frontend/public/data', args.directory / 'data', dirs_exist_ok=True)
    else:
        restored = restore(args.directory)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output: output.write(f'restored={str(restored).lower()}\n')
        print(json.dumps({'restored': restored, 'fallback_to_full_build': not restored}))
