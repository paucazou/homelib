#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende
"""Keeping Library.db in git.

Two rhythms, as asked for:

* every add / edit / removal produces a **local commit**, so nothing is ever a
  single corrupted file away from being lost;
* a **push** happens once a day, and only when there is actually something to
  send.

Commits are debounced rather than immediate.  Cataloguing is done in bursts --
you sit down and enter thirty books at once -- and one commit per book would
bury the history and make every save wait on a Pi Zero writing a megabyte of
SQL.  Instead the writes are coalesced: the commit lands once you have stopped
typing for a couple of minutes, or after ten minutes of continuous work,
whichever comes first.

Alongside the binary Library.db we commit a plain SQL dump.  git cannot diff a
sqlite file, so without the dump the history records only that *something*
changed; with it you can read exactly which book moved shelf.
"""

import datetime
import logging
import os
import sqlite3
import subprocess
import threading

log = logging.getLogger("homelib.gitsync")


class GitError(RuntimeError):
    pass


class GitSync:
    def __init__(self, repo_dir, db_path, dump_path, remote="origin",
                 branch="master", debounce=120, max_delay=600, ssh_key=None,
                 retry_base=60):
        self.repo_dir = os.path.abspath(repo_dir)
        self.db_path = os.path.abspath(db_path)
        self.dump_path = os.path.abspath(dump_path)
        self.remote = remote
        self.branch = branch
        self.debounce = debounce
        self.max_delay = max_delay
        self.ssh_key = ssh_key
        # After a failure the pending work is already overdue, so without a
        # pause the loop would retry as fast as the disk allows.
        self.retry_base = retry_base

        self._lock = threading.Lock()
        self._commit_lock = threading.RLock()
        self._failures = 0
        self._retry_at = None
        self._pending = []           # change summaries awaiting a commit
        self._first_pending_at = None
        self._last_note_at = None
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        # Surfaced in the UI so a silent failure cannot go unnoticed.
        self.last_error = None
        self.last_commit_at = None
        self.last_push_at = None
        self.diverged = False

    # ------------------------------------------------------------ git plumbing

    def _git(self, *args, check=True):
        env = dict(os.environ)
        if self.ssh_key:
            # Pin the deploy key explicitly: the service account has no ssh
            # agent and no ~/.ssh/config we can rely on.
            env["GIT_SSH_COMMAND"] = (
                "ssh -i {} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
                .format(self.ssh_key))
        proc = subprocess.run(
            ("git", "-C", self.repo_dir) + args,
            capture_output=True, text=True, env=env, timeout=300)
        if check and proc.returncode != 0:
            raise GitError("git {}: {}".format(
                " ".join(args), (proc.stderr or proc.stdout).strip()))
        return proc

    def _has_changes(self):
        return bool(self._git("status", "--porcelain",
                              "--", self.db_path, self.dump_path).stdout.strip())

    def write_dump(self):
        """Write the readable SQL mirror of the database.

        Done from a read-only connection: a dump must never be the thing that
        locks out a save.
        """
        uri = "file:{}?mode=ro".format(self.db_path)
        conn = sqlite3.connect(uri, uri=True, timeout=30)
        try:
            tmp = self.dump_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                for line in conn.iterdump():
                    f.write(line + "\n")
            os.replace(tmp, self.dump_path)  # never leave a half-written dump
        finally:
            conn.close()

    # -------------------------------------------------------------- commit job

    def note(self, summary):
        """Record that the database changed.  Called from request threads."""
        now = datetime.datetime.now()
        with self._lock:
            self._pending.append(summary)
            self._last_note_at = now
            if self._first_pending_at is None:
                self._first_pending_at = now
        self._wake.set()

    def _commit_message(self, summaries):
        """A message in the style of the repository's existing history."""
        if len(summaries) == 1:
            title = summaries[0][0].upper() + summaries[0][1:]
        else:
            title = "Mise à jour de la bibliothèque ({} modifications)".format(
                len(summaries))
        body = "\n".join("- " + s for s in summaries)
        return "{}\n\n{}\n".format(title, body) if len(summaries) > 1 else title

    def commit(self):
        """Commit whatever is pending.  Returns the summaries committed.

        Serialised by its own lock: the debounce thread, a POST /api/sync and
        the shutdown flush can all reach here at once, and two `git commit`
        runs in one repository collide on index.lock.
        """
        with self._commit_lock:
            return self._commit()

    def _commit(self):
        with self._lock:
            summaries, self._pending = self._pending, []
            first_at, self._first_pending_at = self._first_pending_at, None
        if not summaries:
            return []
        try:
            self.write_dump()
            self._git("add", "--", self.db_path, self.dump_path)
            if not self._git("diff", "--cached", "--quiet",
                             check=False).returncode:
                # Nothing actually differs -- e.g. an edit that restored the
                # previous value.  Not an error, just nothing to record.
                return []
            self._git("commit", "-m", self._commit_message(summaries))
            self.last_commit_at = datetime.datetime.now()
            self.last_error = None
            self._failures = 0
            self._retry_at = None
            log.info("committed %d change(s)", len(summaries))
            return summaries
        except (GitError, OSError, sqlite3.Error) as exc:
            # Put the summaries back so the next attempt still describes them --
            # and with them the timestamp they were queued at.  Restoring the
            # list but not the timestamp left _run subtracting from None, which
            # killed the committer thread outright and silently stopped every
            # later commit and push.
            with self._lock:
                self._pending = summaries + self._pending
                if self._first_pending_at is None:
                    self._first_pending_at = first_at or datetime.datetime.now()
                if self._last_note_at is None:
                    self._last_note_at = self._first_pending_at
            self._failures += 1
            backoff = min(self.retry_base * (2 ** (self._failures - 1)), 900)
            self._retry_at = datetime.datetime.now() + datetime.timedelta(seconds=backoff)
            self.last_error = str(exc)
            log.error("commit failed (retry in %ss): %s", backoff, exc)
            return []

    def _run(self):
        """Commit once the writes have stopped coming.

        The wait is computed from the deadlines rather than being a fixed tick:
        sleeping a round number of seconds and re-checking would either commit
        late by up to that interval, or spin.  A new write sets the event, the
        loop wakes, and the deadlines are recomputed from it.
        """
        while not self._stop.is_set():
            try:
                with self._lock:
                    if self._pending:
                        now = datetime.datetime.now()
                        started = self._first_pending_at or now
                        last = self._last_note_at or now
                        wait = min(self.debounce - (now - last).total_seconds(),
                                   self.max_delay - (now - started).total_seconds())
                        if self._retry_at:
                            wait = max(wait, (self._retry_at - now).total_seconds())
                    else:
                        wait = None

                if wait is not None and wait <= 0:
                    self.commit()
                    continue
            except Exception as exc:      # never let this thread die
                self.last_error = str(exc)
                log.exception("commit loop error")
                self._stop.wait(30)
                continue

            # No pending work: wake on the next write, with a slow tick as a
            # backstop in case an event is ever missed.
            self._wake.wait(timeout=max(wait, 0.05) if wait is not None else 30)
            self._wake.clear()

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(
                target=self._run, name="gitsync", daemon=True)
            self._thread.start()
        return self

    def stop(self):
        """Flush before going away, so a restart never drops a book."""
        self._stop.set()
        self._wake.set()
        self.commit()

    # ---------------------------------------------------------------- pushing

    def push(self, force_commit=True):
        """Send local commits to the remote, if there are any and it is safe.

        Refuses to push when the remote has moved on independently.  The web app
        is the source of truth for the data, but silently discarding somebody
        else's commit is not a decision this timer gets to make on its own -- it
        reports the divergence and leaves it to a human.
        """
        if force_commit:
            self.commit()
        try:
            self._git("fetch", self.remote, self.branch)
            counts = self._git(
                "rev-list", "--left-right", "--count",
                "{}/{}...HEAD".format(self.remote, self.branch)).stdout.split()
            behind, ahead = int(counts[0]), int(counts[1])

            if behind and ahead:
                self.diverged = True
                self.last_error = (
                    "Le dépôt distant a divergé ({} commit(s) distant(s), "
                    "{} local(aux)) : intervention manuelle nécessaire.".format(
                        behind, ahead))
                log.error(self.last_error)
                return {"pushed": False, "ahead": ahead, "behind": behind,
                        "diverged": True}

            self.diverged = False
            if behind and not ahead:
                # Someone committed from the desktop; take their work.
                self._git("merge", "--ff-only", "{}/{}".format(self.remote, self.branch))
                return {"pushed": False, "ahead": 0, "behind": 0,
                        "fast_forwarded": behind}

            if not ahead:
                return {"pushed": False, "ahead": 0, "behind": 0}

            self._git("push", self.remote, "HEAD:{}".format(self.branch))
            self.last_push_at = datetime.datetime.now()
            self.last_error = None
            log.info("pushed %d commit(s)", ahead)
            return {"pushed": True, "ahead": ahead, "behind": 0}
        except GitError as exc:
            self.last_error = str(exc)
            log.error("push failed: %s", exc)
            return {"pushed": False, "error": str(exc)}

    # ----------------------------------------------------------------- status

    def status(self):
        with self._lock:
            pending = len(self._pending)
        info = {
            "pending": pending,
            "last_commit": self.last_commit_at.isoformat(timespec="seconds")
                            if self.last_commit_at else None,
            "last_push": self.last_push_at.isoformat(timespec="seconds")
                         if self.last_push_at else None,
            "error": self.last_error,
            "diverged": self.diverged,
        }
        try:
            info["head"] = self._git("log", "-1", "--pretty=%h %s").stdout.strip()
            counts = self._git(
                "rev-list", "--left-right", "--count",
                "{}/{}...HEAD".format(self.remote, self.branch),
                check=False)
            if counts.returncode == 0:
                behind, ahead = counts.stdout.split()
                info["behind"] = int(behind)
                info["unpushed"] = int(ahead)
            info["remote"] = self._git(
                "remote", "get-url", self.remote, check=False).stdout.strip()
        except (GitError, ValueError) as exc:
            info["error"] = info["error"] or str(exc)
        return info
