#!/usr/bin/env bash
set -euo pipefail
ROOT=$(realpath "${1:?Usage: install.sh PROJECT_ROOT}")
BASE=/opt/global-news
NODE_VERSION=24.21.0
RSSHUB_COMMIT=67305a500b0c90fba23a9155440ed28d2b011a6b
test "$(id -u)" = 0 || { printf 'Run as root inside Ubuntu.\n'; exit 1; }
test "$(uname -m)" = x86_64 || { printf 'This installer pins Linux x64 binaries.\n'; exit 1; }
test "$(ps -p 1 -o comm=)" = systemd || { printf 'WSL systemd is required.\n'; exit 1; }
test -f "$ROOT/backend/requirements.txt"
if ! dpkg-query -W -f='${Status}\n' postgresql-16 python3-venv nginx-light 2>/dev/null | awk 'BEGIN { ok=1; n=0 } { n++; if ($0 != "install ok installed") ok=0 } END { exit !(ok && n == 3) }'; then
  made_policy=0
  if [ ! -e /usr/sbin/policy-rc.d ]; then
    printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
    chmod 755 /usr/sbin/policy-rc.d
    made_policy=1
  fi
  trap 'if [ "$made_policy" = 1 ]; then rm -f /usr/sbin/policy-rc.d; fi' EXIT
  export DEBIAN_FRONTEND=noninteractive
  timeout 180 apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=20 update
  timeout 300 apt-get -y -o Acquire::Retries=1 -o Acquire::http::Timeout=20 install postgresql-16 python3-venv nginx-light ca-certificates xz-utils
  if [ "$made_policy" = 1 ]; then rm -f /usr/sbin/policy-rc.d; made_policy=0; fi
fi
for account in news-app news-miniflux news-rsshub; do
  if ! id "$account" >/dev/null 2>&1; then
    useradd --system --user-group --home-dir "/var/lib/$account" --create-home --shell /usr/sbin/nologin "$account"
  fi
done
install -d -m 755 "$BASE/bin" "$BASE/downloads" "$BASE/vendor"
if [ ! -x "$BASE/venv/bin/python" ]; then python3 -m venv "$BASE/venv"; fi
"$BASE/venv/bin/pip" install --disable-pip-version-check --timeout 30 --retries 2 -r "$ROOT/backend/requirements.txt"
if [ ! -x "$BASE/bin/miniflux-2.3.3" ]; then
  curl -fL --retry 2 --connect-timeout 15 --max-time 180 https://github.com/miniflux/v2/releases/download/2.3.3/miniflux-linux-amd64 -o "$BASE/downloads/miniflux-2.3.3"
  printf '237bf0aed05e86c235b6bcfbad843bfc7bcdd6a628ece672eae3d1e013ddd244  %s\n' "$BASE/downloads/miniflux-2.3.3" | sha256sum -c -
  install -m 755 "$BASE/downloads/miniflux-2.3.3" "$BASE/bin/miniflux-2.3.3"
fi
if [ ! -x "$BASE/vendor/node-v$NODE_VERSION-linux-x64/bin/node" ]; then
  curl -fL --retry 2 --connect-timeout 15 --max-time 180 "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-x64.tar.xz" -o "$BASE/downloads/node.tar.xz"
  printf 'fd8e59d5a511510f6a298afb548f18c7d2b1be404d8b4a27d94fbe49f56cb2d6  %s\n' "$BASE/downloads/node.tar.xz" | sha256sum -c -
  tar -xJf "$BASE/downloads/node.tar.xz" -C "$BASE/vendor"
fi
export PATH="$BASE/vendor/node-v$NODE_VERSION-linux-x64/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
if [ ! -x "$BASE/vendor/node-v$NODE_VERSION-linux-x64/bin/pnpm" ]; then
  npm install --global --prefix "$BASE/vendor/node-v$NODE_VERSION-linux-x64" pnpm@10.34.5 --no-audit --no-fund
fi
RSSHUB="$BASE/vendor/rsshub-$RSSHUB_COMMIT"
if [ ! -d "$RSSHUB" ]; then
  curl -fL --retry 2 --connect-timeout 15 --max-time 180 "https://codeload.github.com/DIYgod/RSSHub/tar.gz/$RSSHUB_COMMIT" -o "$BASE/downloads/rsshub-$RSSHUB_COMMIT.tar.gz"
  install -d -o news-rsshub -g news-rsshub "$RSSHUB"
  tar -xzf "$BASE/downloads/rsshub-$RSSHUB_COMMIT.tar.gz" --strip-components=1 -C "$RSSHUB"
  chown -R news-rsshub:news-rsshub "$RSSHUB"
fi
if [ ! -f "$RSSHUB/.news-build-complete" ]; then
  cd "$RSSHUB"
  runuser -u news-rsshub -- env PATH="$PATH" HOME=/var/lib/news-rsshub PUPPETEER_SKIP_DOWNLOAD=true PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 HUSKY=0 pnpm install --frozen-lockfile
  runuser -u news-rsshub -- env PATH="$PATH" HOME=/var/lib/news-rsshub PUPPETEER_SKIP_DOWNLOAD=true PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 HUSKY=0 pnpm build
  touch "$RSSHUB/.news-build-complete"
fi
python3 "$ROOT/scripts/native/manage.py" configure "$ROOT"
printf '\nNative runtime installed. No Docker data was modified.\n'
