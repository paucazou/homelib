#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende
"""The daily push, run by homelib-push.timer.

It asks the running web application to do the work, because that process is the
one holding the descriptions of what changed -- "livre ajouté : Les Pensées"
rather than a bare "mise à jour".  If the application is not running (the Pi was
rebooted, the service failed), it falls back to committing and pushing whatever
is on disk, so an outage never means a day's cataloguing sits unsent.

Exits non-zero only on a real failure, so `systemctl status homelib-push` tells
the truth.
"""

import json
import os
import sys
import urllib.error
import urllib.request

APP_URL = os.environ.get("HOMELIB_URL", "http://127.0.0.1:8001") + "/api/sync"
REPO = os.environ.get("HOMELIB_REPO",
                      os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def through_the_app():
    """Returns the app's answer, or None if it is not reachable."""
    request = urllib.request.Request(APP_URL, data=b"", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # The app answered, and said no. That is an answer, not an outage.
        try:
            return json.loads(exc.read().decode("utf-8"))
        except Exception:
            return {"error": "HTTP {}".format(exc.code)}
    except (urllib.error.URLError, OSError, ValueError):
        return None


def directly():
    sys.path.insert(0, REPO)
    from webapp.gitsync import GitSync

    sync = GitSync(
        REPO,
        os.environ.get("HOMELIB_DB", os.path.join(REPO, "Library.db")),
        os.environ.get("HOMELIB_DUMP", os.path.join(REPO, "Library.sql")),
        remote=os.environ.get("HOMELIB_GIT_REMOTE", "origin"),
        branch=os.environ.get("HOMELIB_GIT_BRANCH", "master"),
        ssh_key=os.environ.get("HOMELIB_SSH_KEY") or None)
    # Nothing is pending in this fresh process, so give the commit a name of
    # its own rather than letting it be skipped.
    sync.note("mise à jour quotidienne de la base")
    return sync.push()


def main():
    result = through_the_app()
    if result is None:
        print("application injoignable, synchronisation directe", file=sys.stderr)
        result = directly()

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))

    if result.get("diverged"):
        print("le dépôt distant a divergé : intervention manuelle nécessaire",
              file=sys.stderr)
        return 1
    if result.get("error"):
        print(result["error"], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
