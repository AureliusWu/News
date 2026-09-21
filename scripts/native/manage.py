"""Root-only, project-scoped Ubuntu/systemd service controller; no Docker calls."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import pwd
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request

BASE = Path('/opt/global-news')
ETC = Path('/etc/global-news')
STATE = Path('/var/lib/global-news')
UNITS = ['postgresql@16-news.service', 'postgresql@16-newsminiflux.service',
         'news-miniflux.service', 'news-rsshub.service', 'news-backend.service',
         'news-worker.service', 'news-frontend.service']
NODE = BASE / 'vendor/node-v24.21.0-linux-x64/bin/node'
RSSHUB = BASE / 'vendor/rsshub-67305a500b0c90fba23a9155440ed28d2b011a6b'


def run(args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def write(path: Path, content: str, mode: int = 0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
        stream.write(content)
    path.chmod(mode)


def load_env(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#'):
            key, value = line.split('=', 1)
            result[key] = value.strip('"')
    return result


def save_env(name: str, values: dict[str, str]):
    if any('\n' in value or '"' in value or '\\' in value for value in values.values()):
        raise ValueError('Unsupported environment value; refusing unsafe systemd quoting')
    write(ETC / name, ''.join(f'{key}="{value}"\n' for key, value in values.items()), 0o600)


def database(cluster: str, port: int, role: str, password: str, name: str):
    cluster_config = Path(f'/etc/postgresql/16/{cluster}')
    if not cluster_config.exists():
        run(['pg_createcluster', '16', cluster, '--port', port, '--start-conf', 'manual',
             '--', '--auth-local=peer', '--auth-host=scram-sha-256'])
    run(['systemctl', 'start', f'postgresql@16-{cluster}.service'])
    # Credentials go through stdin, never command arguments or captured diagnostics.
    sql = rf"""DO $$ BEGIN
IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN
  CREATE ROLE {role} LOGIN PASSWORD '{password}';
END IF;
END $$;
SELECT 'CREATE DATABASE {name} OWNER {role}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '{name}') \gexec
"""
    result = subprocess.run(['runuser', '-u', 'postgres', '--', 'psql', '-p', str(port),
                             '-v', 'ON_ERROR_STOP=1', '-d', 'postgres'],
                            input=sql, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f'Database initialization failed for {cluster}; private SQL omitted')


def service(name: str, account: str, cwd: Path, command: str, after: str,
            environment: str = '', pre: str = '', extra: str = ''):
    write(Path('/etc/systemd/system') / f'{name}.service', f'''[Unit]
Description=Global News native {name}
After=network.target {after}
Wants={after}
StartLimitIntervalSec=0

[Service]
Type=simple
User={account}
Group={account}
WorkingDirectory={cwd}
{environment}
{pre}
ExecStart={command}
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
UMask=0027
{extra}

[Install]
WantedBy=multi-user.target
''')


def configure(root: Path):
    root = root.resolve(strict=True)
    if any(c in str(root) for c in '\n"%'):
        raise ValueError('Project path contains unsupported systemd characters')
    ETC.mkdir(mode=0o700, parents=True, exist_ok=True)
    ETC.chmod(0o700)
    STATE.mkdir(mode=0o755, parents=True, exist_ok=True)
    identity = ETC / 'identity.json'
    if identity.exists():
        values = json.loads(identity.read_text())
        if values['project'] != str(root):
            raise RuntimeError('This native runtime belongs to a different project')
    else:
        values = {'project': str(root), 'app_password': secrets.token_hex(32),
                  'miniflux_password': secrets.token_hex(32), 'admin_password': secrets.token_hex(32)}
        write(identity, json.dumps(values), 0o600)
    database('news', 55432, 'news_native', values['app_password'], 'news_native')
    database('newsminiflux', 55433, 'miniflux_native', values['miniflux_password'], 'miniflux_native')
    save_env('app.env', {
        'APP_ENV': 'local', 'APP_VERSION': '0.2.0', 'APP_BASE_PATH': '',
        'DATABASE_URL': f"postgresql+asyncpg://news_native:{values['app_password']}@127.0.0.1:55432/news_native",
        'MINIFLUX_URL': 'http://127.0.0.1:8081', 'MINIFLUX_ADMIN_USERNAME': 'news-admin',
        'MINIFLUX_ADMIN_PASSWORD': values['admin_password'], 'RSSHUB_URL': 'http://127.0.0.1:1200',
        'SOURCE_REGISTRY_PATH': str(root / 'config/sources.yaml'),
        'NEWS_SYNC_INTERVAL_SECONDS': '60', 'NEWS_INITIAL_LOOKBACK_DAYS': '5',
        'NEWS_INITIAL_FULL_REFRESH': 'false', 'NEWS_PAGE_SIZE': '100',
        'PYTHONPATH': f'{root / "backend"}:{root}', 'PYTHONDONTWRITEBYTECODE': '1',
        'PYTHONUNBUFFERED': '1',
    })
    save_env('miniflux.env', {
        'DATABASE_URL': f"postgres://miniflux_native:{values['miniflux_password']}@127.0.0.1:55433/miniflux_native?sslmode=disable",
        'RUN_MIGRATIONS': '1', 'CREATE_ADMIN': '1', 'ADMIN_USERNAME': 'news-admin',
        'ADMIN_PASSWORD': values['admin_password'], 'LISTEN_ADDR': '127.0.0.1:8081',
        'BASE_URL': 'http://127.0.0.1:8081', 'POLLING_SCHEDULER': 'entry_frequency',
        'POLLING_FREQUENCY': '1', 'SCHEDULER_ENTRY_FREQUENCY_MIN_INTERVAL': '5',
        'SCHEDULER_ENTRY_FREQUENCY_MAX_INTERVAL': '60', 'POLLING_LIMIT_PER_HOST': '2',
        'BATCH_SIZE': '10', 'WORKER_POOL_SIZE': '4', 'HTTP_CLIENT_TIMEOUT': '20',
        'POLLING_PARSING_ERROR_LIMIT': '0', 'FETCHER_ALLOW_PRIVATE_NETWORKS': '1',
        'LOG_FORMAT': 'json',
    })
    save_env('rsshub.env', {'NODE_ENV': 'production', 'PORT': '1200',
                          'LISTEN_INADDR_ANY': '0', 'DISABLE_IPV6': '1',
                          'CACHE_TYPE': 'memory', 'CACHE_EXPIRE': '600',
                          'REQUEST_TIMEOUT': '15000', 'PUPPETEER_SKIP_DOWNLOAD': 'true'})
    service('news-miniflux', 'news-miniflux', STATE, str(BASE / 'bin/miniflux-2.3.3'),
            'postgresql@16-newsminiflux.service',
            f'EnvironmentFile={ETC}/miniflux.env\nEnvironmentFile=-{ETC}/proxy.env')
    service('news-rsshub', 'news-rsshub', RSSHUB, f'{NODE} --max-http-header-size=32768 dist/index.mjs',
            '', f'EnvironmentFile={ETC}/rsshub.env', extra='MemoryMax=1536M')
    service('news-backend', 'news-app', root / 'backend',
            f'{BASE}/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
            'postgresql@16-news.service', f'EnvironmentFile={ETC}/app.env',
            pre=f'ExecStartPre={BASE}/venv/bin/alembic upgrade head')
    service('news-worker', 'news-app', root,
            f'{BASE}/venv/bin/python -m worker.sync_feeds',
            'news-backend.service news-miniflux.service', f'EnvironmentFile={ETC}/app.env')
    service('news-frontend', 'news-app', STATE, f'/usr/sbin/nginx -c {ETC}/nginx.conf -g "daemon off;"',
            'news-backend.service', extra='RuntimeDirectory=news-frontend\nReadWritePaths=/run/news-frontend')
    # Nginx runs unprivileged; its configuration contains no credentials.
    write(STATE / 'nginx.conf', '''pid /run/news-frontend/nginx.pid;
error_log stderr warn;
worker_processes 1;
events { worker_connections 1024; }
http {
  include /etc/nginx/mime.types;
  default_type application/octet-stream;
  access_log syslog:server=unix:/dev/log,tag=news_frontend combined;
  sendfile on;
  server_tokens off;
  client_body_temp_path /run/news-frontend/body;
  proxy_temp_path /run/news-frontend/proxy;
  fastcgi_temp_path /run/news-frontend/fastcgi;
  uwsgi_temp_path /run/news-frontend/uwsgi;
  scgi_temp_path /run/news-frontend/scgi;
  server {
    listen 127.0.0.1:8080;
    server_name localhost;
    root /var/lib/global-news/frontend;
    index index.html;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    location /api/v1/ {
      proxy_pass http://127.0.0.1:8000;
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-Proto $scheme;
      proxy_connect_timeout 5s;
      proxy_read_timeout 20s;
    }
    location = /api/health { proxy_pass http://127.0.0.1:8000/health; }
    location = /api/ready { proxy_pass http://127.0.0.1:8000/ready; }
    location /api/ { return 404; }
    location = /sw.js { add_header Cache-Control "no-cache"; }
    location = /index.html { add_header Cache-Control "no-cache"; }
    location / { try_files $uri $uri/ /index.html; }
  }
}
''')
    # The secret directory is root-only; expose only the non-secret nginx config.
    unit = Path('/etc/systemd/system/news-frontend.service')
    write(unit, f'''[Unit]
Description=Global News native frontend
After=news-backend.service
Wants=news-backend.service
[Service]
Type=simple
User=news-app
Group=news-app
ExecStart=/usr/sbin/nginx -c {STATE}/nginx.conf -g "daemon off;"
Restart=on-failure
RestartSec=5
RuntimeDirectory=news-frontend
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/run/news-frontend
[Install]
WantedBy=multi-user.target
''')
    write(ETC / 'project', str(root) + '\n', 0o600)
    run(['systemctl', 'daemon-reload'])


def project() -> Path:
    return Path((ETC / 'project').read_text().strip())


def application(args, cwd=None):
    environment = os.environ.copy()
    environment.update(load_env(ETC / 'app.env'))
    account = pwd.getpwnam('news-app')
    environment['HOME'] = account.pw_dir
    environment['USER'] = account.pw_name
    environment['LOGNAME'] = account.pw_name
    result = subprocess.run([str(BASE / 'venv/bin/python'), *args], env=environment,
                            cwd=cwd or project(), user=account.pw_uid, group=account.pw_gid)
    return result.returncode


def status():
    result = {}
    for unit in UNITS:
        state = subprocess.run(['systemctl', 'is-active', unit], text=True, capture_output=True)
        result[unit] = state.stdout.strip()
    for label, url in {'backend': 'http://127.0.0.1:8000/ready',
                       'miniflux': 'http://127.0.0.1:8081/healthcheck',
                       'rsshub': 'http://127.0.0.1:1200/healthz',
                       'frontend': 'http://127.0.0.1:8080/'}.items():
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                result[label + '_http'] = response.status
        except Exception as exc:
            result[label + '_http'] = type(exc).__name__
    pid = subprocess.run(['systemctl', 'show', 'news-worker', '-p', 'MainPID', '--value'],
                         capture_output=True, text=True).stdout.strip()
    heartbeat = Path(f'/proc/{pid}/root/tmp/news-worker-heartbeat')
    result['worker_heartbeat_age_seconds'] = round(time.time() - heartbeat.stat().st_mtime, 1) if heartbeat.exists() else None
    print(json.dumps(result, indent=2))
    healthy = all(result[unit] == 'active' for unit in UNITS)
    healthy &= all(result[label + '_http'] == 200 for label in ('backend', 'miniflux', 'rsshub', 'frontend'))
    healthy &= result['worker_heartbeat_age_seconds'] is not None and result['worker_heartbeat_age_seconds'] < 120
    return 0 if healthy else 1


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run this controller through scripts/Native.ps1 or sudo.')
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['configure', 'start', 'stop', 'restart', 'status', 'logs',
                                         'build', 'test-backend', 'validate-sources', 'verify-pipeline'])
    parser.add_argument('root', nargs='?')
    args = parser.parse_args()
    if args.action == 'configure':
        configure(Path(args.root))
    elif args.action in ('start', 'stop', 'restart'):
        units = list(reversed(UNITS)) if args.action == 'stop' else UNITS
        run(['systemctl', args.action, *units])
    elif args.action == 'build':
        source = project() / 'frontend/dist'
        if not (source / 'index.html').is_file():
            raise RuntimeError('Build frontend first; existing served files were not changed')
        shutil.copytree(source, STATE / 'frontend', dirs_exist_ok=True)
    elif args.action == 'status':
        return status()
    elif args.action == 'logs':
        run(['journalctl', '--no-pager', '-n', '60', '-u', 'news-backend', '-u', 'news-worker',
             '-u', 'news-miniflux', '-u', 'news-rsshub', '-u', 'news-frontend'])
    elif args.action == 'test-backend':
        return application(['-m', 'pytest', '-q', '-p', 'no:cacheprovider'], project() / 'backend')
    elif args.action == 'validate-sources':
        return application(['-m', 'worker.validate_sources', '--report', str(project() / 'docs/V0.2_SOURCE_HEALTH.md')])
    elif args.action == 'verify-pipeline':
        return application(['-m', 'worker.verify_pipeline', '--base-url', 'http://127.0.0.1:8080'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
