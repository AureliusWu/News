"""Provision a loopback-only OpenSSH reverse-forward endpoint for WSL NAT."""
from __future__ import annotations

import json
import os
from pathlib import Path
import pwd
import re
import socket
import subprocess
import sys

ETC = Path('/etc/global-news')
HOME = Path('/var/lib/news-proxy')
CONFIG = ETC / 'proxy-sshd.conf'


def run(args):
    subprocess.run(args, check=True, stdout=sys.stderr)


def write(path: Path, content: str, mode: int = 0o600):
    fd = os.open(path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, mode)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
        stream.write(content)
    path.chmod(mode)


def install_server():
    if Path('/usr/sbin/sshd').is_file():
        return
    policy = Path('/usr/sbin/policy-rc.d')
    created_policy = not policy.exists()
    if created_policy:
        write(policy, '#!/bin/sh\nexit 101\n', 0o755)
    try:
        subprocess.run(['apt-get', '-y', '--no-install-recommends',
                        '-o', 'Acquire::Retries=1', '-o', 'Acquire::http::Timeout=20',
                        'install', 'openssh-server'], check=True, timeout=300,
                       env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'}, stdout=sys.stderr)
        # Only disable defaults when this invocation installed the server.
        run(['systemctl', 'disable', '--now', 'ssh.service', 'ssh.socket'])
    finally:
        if created_policy:
            policy.unlink()


def configure():
    request = json.loads(sys.stdin.read().lstrip('\ufeff'))
    identity = json.loads((ETC / 'identity.json').read_text())
    if identity['project'] != request['project']:
        raise RuntimeError('Native project identity mismatch')
    key = request['public_key'].strip()
    if not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/=]+(?: [A-Za-z0-9_.@-]+)?', key):
        raise ValueError('Expected one plain Ed25519 public key')
    install_server()
    try:
        account = pwd.getpwnam('news-proxy')
    except KeyError:
        run(['useradd', '--system', '--user-group', '--create-home',
             '--home-dir', str(HOME), '--shell', '/usr/sbin/nologin', 'news-proxy'])
        # '*' cannot match a password; public-key-only SSH requires a non-locked account.
        run(['usermod', '--password', '*', 'news-proxy'])
        account = pwd.getpwnam('news-proxy')
    if account.pw_dir != str(HOME):
        raise RuntimeError('Refusing to reuse an unrelated news-proxy account')
    ssh_dir = HOME / '.ssh'
    ssh_dir.mkdir(mode=0o700, exist_ok=True)
    ssh_dir.chmod(0o700)
    os.chown(ssh_dir, account.pw_uid, account.pw_gid)
    authorized = ssh_dir / 'authorized_keys'
    write(authorized, 'restrict,port-forwarding,permitlisten="127.0.0.1:17890" ' + key + '\n')
    os.chown(authorized, account.pw_uid, account.pw_gid)
    host_key = ETC / 'proxy_host_ed25519_key'
    if not host_key.exists():
        run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(host_key)])
    # The sandbox resolves ReadWritePaths before ExecStartPre. Provision the
    # shared privilege-separation directory now and at boot, without deleting it.
    tmpfiles = Path('/etc/tmpfiles.d/news-proxy-sshd.conf')
    write(tmpfiles, 'd /run/sshd 0755 root root -\n', 0o644)
    run(['systemd-tmpfiles', '--create', str(tmpfiles)])
    write(CONFIG, f'''Port 12222
ListenAddress 127.0.0.1
AddressFamily inet
HostKey {host_key}
PidFile /run/news-proxy-sshd/sshd.pid
AuthorizedKeysFile .ssh/authorized_keys
AllowUsers news-proxy
AuthenticationMethods publickey
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
UsePAM no
StrictModes yes
AllowTcpForwarding remote
AllowStreamLocalForwarding no
PermitListen 127.0.0.1:17890
GatewayPorts no
AllowAgentForwarding no
X11Forwarding no
PermitTTY no
PermitTunnel no
PermitUserRC no
MaxSessions 0
LogLevel ERROR
''')
    write(Path('/etc/systemd/system/news-proxy-sshd.service'), f'''[Unit]
Description=Global News loopback-only proxy tunnel
After=network.target systemd-tmpfiles-setup.service
StartLimitIntervalSec=0
[Service]
Type=simple
ExecStartPre=/usr/bin/install -d -m 0755 /run/sshd
ExecStartPre=/usr/sbin/sshd -t -f {CONFIG}
ExecStart=/usr/sbin/sshd -D -e -f {CONFIG}
Restart=on-failure
RestartSec=5
RuntimeDirectory=news-proxy-sshd
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/run/news-proxy-sshd /run/sshd
[Install]
WantedBy=multi-user.target
''', 0o644)
    # Do not enable this unit globally; Native.ps1 owns its start/stop lifecycle.
    run(['systemctl', 'daemon-reload'])
    run(['systemctl', 'start', 'news-proxy-sshd.service'])
    print(json.dumps({'host_key': host_key.with_name(host_key.name + '.pub').read_text().strip()}))


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run through Proxy-Tunnel.ps1.')
    action = sys.argv[1]
    if action == 'configure':
        configure()
    elif action == 'check':
        try:
            with socket.create_connection(('127.0.0.1', 17890), timeout=2):
                pass
        except OSError:
            return 1
    elif action == 'enable':
        write(ETC / 'proxy.env', 'HTTP_PROXY=http://127.0.0.1:17890\n'
              'HTTPS_PROXY=http://127.0.0.1:17890\nNO_PROXY=localhost,127.0.0.1,::1\n')
        run(['systemctl', 'restart', 'news-miniflux.service'])
    else:
        raise SystemExit('Unsupported action')
    return 0


if __name__ == '__main__':
    sys.exit(main())
