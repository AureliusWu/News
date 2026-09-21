# Optional WSL loopback proxy tunnel

## Purpose

WSL2 NAT cannot automatically reach a Windows proxy bound only to Windows
`127.0.0.1`. On 2026-09-16 a Windows BBC feed request succeeded while the same
request from Miniflux timed out. Direct access to the Windows NAT gateway proxy
port also timed out. This transport preserves the existing Windows proxy and
does not change `.wslconfig`, restart WSL, enable proxy LAN access, add firewall
exceptions, or bind a service to a public/LAN address.

## Install and lifecycle (PowerShell 7.3+)

```powershell
.\scripts\Proxy-Tunnel.ps1 -Action Install -ProxyPort 7890
.\scripts\Proxy-Tunnel.ps1 -Action Status
.\scripts\Native.ps1 -Action Start
.\scripts\Native.ps1 -Action Stop
```

Install requires the existing local Windows proxy to be running. Native Start
starts the configured tunnel before the application; Native Stop stops its own
SSH process and dedicated SSH server. A repeated Install reuses the dedicated
keys. It does not reuse personal SSH identities or SSH configuration.

Transport:

```text
Miniflux -> WSL 127.0.0.1:17890
         -> authenticated reverse SSH forwarding
         -> Windows 127.0.0.1:7890 -> existing proxy -> official feeds
```

Windows OpenSSH connects to WSL's dedicated `127.0.0.1:12222` listener through
normal WSL localhost forwarding. The reverse forward listens only on WSL
loopback. Both HTTP_PROXY and HTTPS_PROXY are scoped to Miniflux, with localhost
in NO_PROXY so RSSHub and internal endpoints are not sent through the proxy.

## Security and state

- The dedicated `news-proxy` account has no login shell and no usable password.
- Public-key authentication only; password and keyboard-interactive login are disabled.
- `MaxSessions 0` prevents shell and subsystem sessions.
- Only remote TCP forwarding to the fixed `127.0.0.1:17890` listener is permitted.
- Agent, X11, Unix-socket and tunnel-device forwarding are disabled.
- Strict host-key checking uses a host key obtained locally during provisioning.
- Client keys, host pin, PID/start-time state and SSH diagnostics stay under the
  current user's `%LOCALAPPDATA%/GlobalNewsNative/News-Proxy`, outside the repository.
- Private client key ACL is restricted to the current Windows user and SYSTEM.
- SSH server key and proxy environment remain in root-only `/etc/global-news`.
- When OpenSSH Server is newly installed, its default SSH service/socket are
  disabled before starting the separate loopback-only instance. An existing
  system SSH installation is not reconfigured.

The Windows proxy must remain running. This local setup does not provide cloud
availability while the PC sleeps or is off. If the SSH connection exits after
a network/WSL interruption, Native Start reconnects it; there is no Windows
login task or permanent Windows service installed. Native Status and source
health validation should both be checked: an alive process is not evidence of
successful upstream requests.

References:

- [OpenSSH reverse forwarding and no-command mode](https://man.openbsd.org/ssh)
- [OpenSSH forwarding restrictions and MaxSessions](https://man.openbsd.org/sshd_config)

## 2026-09-16 observed status

The SSH endpoint startup directory ordering was fixed with a project-owned
systemd-tmpfiles rule. The loopback tunnel carried a BBC RSS request from WSL
with HTTP 200; Miniflux source coverage increased from 11 to 36 healthy feeds.
No global proxy, firewall rule or LAN exposure was added.

The procedure above is not yet fully lifecycle-accepted. On PowerShell 7.6.5,
JSON timestamps become DateTime objects, while Get-ProxyProcess compares them
as formatted strings. A repeated start lost ownership tracking: the actual
forward continued working, but Status reported that the managed SSH process
was absent. See the open defect and evidence in `V0.2_HANDOFF.md`. Do not infer
safe process ownership from an open forwarding port alone.

## 2026-09-21 lifecycle acceptance closure

The former execution-policy-blocked batch is superseded by the safe regression
`scripts/Test-ProxyLifecycle.ps1`: 16/16 PASS on September 17 and September 21.
Metadata corruption is confined to an ignored test fixture. Exact ownership,
timestamp normalization, stale fixture recovery, foreign-owner refusal,
exclusive locking, real Stop/Start, idempotency and post-restart RSS access all
have passing evidence. The September 21 run replaced owned PID 18932 with owned
PID 18172 and finished with HTTP 200 through the loopback forward.

The test deliberately interrupts outbound feed requests. After testing, refresh
affected Miniflux feeds and validate their actual parsing errors and freshness;
an asynchronous refresh HTTP 204 alone is not acceptance. On September 21,
23 affected subscriptions were refreshed synchronously and all 36 existing
subscriptions had zero parsing errors afterward. Two separately configured,
unavailable feeds remain excluded from healthy coverage.

This tunnel is outbound-only support for the local native runtime. It is not a
public backend, does not make GitHub Pages live, and has not been accepted for
automatic reconnection across host reboot or an unattended overnight run.
Website publication remains paused by explicit user request.

## 2026-09-17 ownership correction (historical)

The previous timestamp/ownership defect is now patched. The controller converts
stored DateTime, DateTimeOffset or string values to UTC ticks, checks the exact
SSH executable and complete managed arguments, and serializes lifecycle commands.
It only adopts an existing process with a matching project fingerprint; a port
without a verified owner is not sufficient evidence. A new process is recorded
only after readiness checks. The repeated Start/Status scenario passed.

The expanded Stop/Start, stale-record injection and conflict tests did not run:
the execution environment rejected the batch command before execution. Those
branches remain unaccepted; the September 16 full-lifecycle warning is narrowed,
not replaced with an all-pass claim. No global proxy, firewall or personal SSH
configuration was changed. See V0.2_HANDOFF.md for the dated evidence.
