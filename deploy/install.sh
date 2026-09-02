#!/bin/bash
# Homelib -- install or update the web application on the Raspberry Pi.
#
# Safe to run again: it creates what is missing, refreshes what changed, and
# leaves the database alone.  Run it from the repository:
#
#     cd ~/philippe/homelib && ./deploy/install.sh
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO/.venv"
KEY="$HOME/.ssh/homelib_deploy"
PORT=8888

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

cd "$REPO"

say "Python environment"
if [ ! -x "$VENV/bin/python" ]; then
    python3 -m venv "$VENV"
    echo "created $VENV"
fi
# --no-cache-dir matters here: pip's cache has filled this Pi's card before.
"$VENV/bin/pip" install --quiet --upgrade --no-cache-dir pip
"$VENV/bin/pip" install --quiet --no-cache-dir -r "$REPO/requirements-web.txt"
"$VENV/bin/python" -c "import flask, gunicorn; print('flask and gunicorn ready')"

say "git identity"
# Commits are made by the machine, so give them a name that says so.
git config user.name  "Homelib (palantir)"
git config user.email "homelib@palantir.local"
git config push.default current

say "Deploy key"
if [ ! -f "$KEY" ]; then
    ssh-keygen -t ed25519 -N "" -C "homelib@palantir" -f "$KEY" >/dev/null
    echo "created a new key"
fi
chmod 600 "$KEY"
echo
echo "  Add this key to GitHub with WRITE access:"
echo "  Settings -> Deploy keys -> Add deploy key -> tick 'Allow write access'"
echo
sed 's/^/    /' "$KEY.pub"
echo

say "Remote"
# Pushing needs ssh; the https URL the clone came from cannot use a deploy key.
current="$(git remote get-url origin 2>/dev/null || echo none)"
case "$current" in
    git@github.com:*) echo "already ssh: $current" ;;
    https://github.com/*)
        ssh_url="git@github.com:${current#https://github.com/}"
        git remote set-url origin "$ssh_url"
        echo "switched origin to $ssh_url"
        ;;
    *) echo "origin is $current -- left as it is" ;;
esac
ssh-keyscan -t ed25519 github.com 2>/dev/null | grep -q . \
    && ssh-keyscan -t ed25519 github.com 2>/dev/null >> "$HOME/.ssh/known_hosts.tmp" \
    && sort -u "$HOME/.ssh/known_hosts.tmp" "$HOME/.ssh/known_hosts" 2>/dev/null \
       > "$HOME/.ssh/known_hosts.new" \
    && mv "$HOME/.ssh/known_hosts.new" "$HOME/.ssh/known_hosts" \
    && rm -f "$HOME/.ssh/known_hosts.tmp" || true

say "systemd units"
sudo install -m 644 "$REPO/deploy/homelib-web.service"  /etc/systemd/system/
sudo install -m 644 "$REPO/deploy/homelib-push.service" /etc/systemd/system/
sudo install -m 644 "$REPO/deploy/homelib-push.timer"   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now homelib-web.service
sudo systemctl enable --now homelib-push.timer
sudo systemctl restart homelib-web.service

say "nginx"
sudo install -m 644 "$REPO/deploy/nginx-homelib.conf" /etc/nginx/sites-available/homelib
sudo ln -sfn /etc/nginx/sites-available/homelib /etc/nginx/sites-enabled/homelib
sudo nginx -t
sudo systemctl reload nginx

say "Checking"
for i in $(seq 1 40); do
    if curl -fsS "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1; then break; fi
    sleep 1
done
curl -fsS "http://127.0.0.1:$PORT/healthz" && echo
echo
echo "Homelib is at  http://$(hostname):$PORT/  (and http://$(hostname).local:$PORT/)"
echo "Logs:          journalctl -u homelib-web -f"
echo "Daily push:    systemctl list-timers homelib-push"
