#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende
"""Data access layer for the Homelib web app.

This module speaks the *existing* Library.db schema without altering it: the
desktop PyQt GUI (gui/) and the command line tool (clfun.py) read the very same
file, so any change of shape here would break them.

What it does change is how rows are resolved.  The older code looks items up by
their position in a list -- ``list_authors[nb]``, ``list_publishers[book[3]-1]``
-- which is only correct while every table's ids run 1..n with no holes.  That
happens to be true today (nothing is ever hard-deleted), but it means a single
removed row would silently re-attribute thousands of books to the wrong author.
Everything below resolves by id instead.

The same constraint is why merging two authors here leaves the losing row in
place, merely orphaned: deleting it would punch the hole that breaks the GUI.
"""

import csv
import os
import sqlite3
import threading

# Author encodings stored in books.author, kept identical to mainclass.Library.
COLLECTIVE = "collective"
ANONYMOUS = "anonymous"

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def column_index(letter):
    """'A' -> 0.  Boxes store their column as a letter, libraries as a count."""
    return ALPHABET.index(letter.upper())


def column_letter(index):
    return ALPHABET[index]


def decode_authors(raw):
    """books.author -> (kind, [author_id, ...]).

    kind is 'anonymous', 'collective' or 'named'.  The stored form for named
    authors is "<count>|<id>|<id>...", the leading count being redundant with
    the list itself but written by every existing client, so we keep it.
    """
    if raw == ANONYMOUS:
        return ANONYMOUS, []
    if raw == COLLECTIVE:
        return COLLECTIVE, []
    parts = [p for p in (raw or "").split("|") if p != ""]
    return "named", [int(p) for p in parts[1:]]


def encode_authors(kind, ids):
    """(kind, ids) -> the string books.author expects."""
    if kind == ANONYMOUS:
        return ANONYMOUS
    if kind == COLLECTIVE:
        return COLLECTIVE
    ids = list(dict.fromkeys(int(i) for i in ids))  # de-duplicate, keep order
    if not ids:
        raise ValueError("a named book needs at least one author")
    return "{}|{}".format(len(ids), "|".join(str(i) for i in ids))


class Library:
    """Thread-safe access to Library.db.

    gunicorn runs this app with a single worker and a handful of threads (a Pi
    Zero has one core), so a lock around writes plus one connection per thread
    is enough; no connection pool, no WAL.  WAL is deliberately avoided because
    it would split the database into -wal/-shm side files, and the whole point
    of this project is that Library.db stays a single file we can commit.
    """

    def __init__(self, path, on_write=None):
        self.path = os.path.abspath(path)
        self._local = threading.local()
        self._write_lock = threading.RLock()
        # Called after every committed write, so the app can schedule a commit.
        self.on_write = on_write

    # ------------------------------------------------------------------ conn

    @property
    def conn(self):
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=15)
            conn.row_factory = sqlite3.Row
            # Writers are serialised by _write_lock, but a stray reader from the
            # desktop GUI syncing the file could still hold a shared lock.
            conn.execute("PRAGMA busy_timeout = 15000")
            conn.execute("PRAGMA foreign_keys = OFF")
            self._local.conn = conn
        return conn

    def close(self):
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def _query(self, sql, args=()):
        return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def _one(self, sql, args=()):
        row = self.conn.execute(sql, args).fetchone()
        return dict(row) if row else None

    def _next_id(self, table):
        """Mirrors mainclass.Library._newID.

        max(id)+1 rather than AUTOINCREMENT because that is what every existing
        row was created with, and reusing the scheme keeps ids contiguous --
        which the desktop GUI still depends on.
        """
        row = self.conn.execute("SELECT max(id) FROM {}".format(table)).fetchone()
        return (row[0] or 0) + 1

    def _touch(self, summary):
        if self.on_write:
            self.on_write(summary)

    # --------------------------------------------------------------- reading

    def libraries(self):
        return self._query("SELECT * FROM libraries ORDER BY name COLLATE NOCASE")

    def boxes(self):
        return self._query("SELECT * FROM boxes ORDER BY name COLLATE NOCASE")

    def authors(self):
        return self._query(
            "SELECT * FROM authors ORDER BY last_name COLLATE NOCASE, "
            "christian_name COLLATE NOCASE")

    def publishers(self):
        return self._query("SELECT * FROM publisher ORDER BY name COLLATE NOCASE")

    def books(self):
        return self._query("SELECT * FROM books")

    def deleted_book_ids(self):
        """Book ids tagged deleted.

        deleted_books is append-only and has picked up a few duplicate entries
        over the years, hence the set.
        """
        return {r["book"] for r in self._query("SELECT book FROM deleted_books")}

    def book(self, book_id):
        return self._one("SELECT * FROM books WHERE id = ?", (book_id,))

    def catalog(self):
        """The whole library, denormalised, plus reference counts.

        The browser filters 3500 books per keystroke locally; asking a Pi Zero
        to do that over HTTP would be visibly slow.  So we ship it all once and
        let the ETag in app.py keep it cached.

        Counting references happens in this same pass on purpose.  Doing it
        separately meant walking all 3500 books twice and decoding every author
        string twice, which on the armv6 board this runs on is a second of work
        for a number we already had in hand.
        """
        author_rows = self.authors()
        # Render "First Last" once per author rather than once per appearance:
        # a well-represented author turns up in dozens of books.
        labels = {a["id"]: self.author_label(a) for a in author_rows}
        publishers = {p["id"]: p["name"] for p in self.publishers()}
        library_rows = self.libraries()
        libraries = {l["id"]: l for l in library_rows}
        box_rows = self.boxes()
        boxes = {b["id"]: b for b in box_rows}
        deleted = self.deleted_book_ids()

        author_use, publisher_use, box_use, library_use = {}, {}, {}, {}

        books = []
        for b in self.books():
            kind, ids = decode_authors(b["author"])
            box = boxes.get(b["box"])
            library = libraries.get(box["library"]) if box else None

            for i in ids:
                author_use[i] = author_use.get(i, 0) + 1
            publisher_use[b["publisher"]] = publisher_use.get(b["publisher"], 0) + 1
            box_use[b["box"]] = box_use.get(b["box"], 0) + 1
            if library is not None:
                library_use[library["id"]] = library_use.get(library["id"], 0) + 1

            books.append({
                "id": b["id"],
                "title": b["name"] or "",
                "author_kind": kind,
                "author_ids": ids,
                # Pre-rendered names so the client never has to join; it only
                # ever substring-matches them.
                "authors": [labels[i] for i in ids if i in labels],
                "publisher_id": b["publisher"],
                "publisher": publishers.get(b["publisher"], ""),
                "more": b["more"] or "",
                "box_id": b["box"],
                "box": box["name"] if box else "",
                "box_ref": "{}{}".format(box["column"], box["line"]) if box else "",
                "library_id": library["id"] if library else None,
                "library": library["name"] if library else "",
                "deleted": b["id"] in deleted,
            })

        return {
            "books": books,
            "authors": [dict(a, label=labels[a["id"]]) for a in author_rows],
            "publishers": [{"id": i, "name": n} for i, n in publishers.items()],
            "boxes": [dict(b, library_name=libraries.get(b["library"], {}).get("name", ""))
                      for b in box_rows],
            "libraries": library_rows,
            # Used to grey out never-referenced rows -- notably the authors left
            # orphaned by a merge, which cannot be deleted (see the module
            # docstring).
            "usage": {"authors": author_use, "publishers": publisher_use,
                      "boxes": box_use, "libraries": library_use},
        }

    @staticmethod
    def author_label(author):
        """Display form.  The DB calls the given name 'christian_name'."""
        return " ".join(p for p in (author["christian_name"], author["last_name"]) if p)

    def books_in_box(self, box_id):
        return self._query("SELECT * FROM books WHERE box = ?", (box_id,))

    # --------------------------------------------------------------- history

    BACKUP_TABLES = {
        "books": "books_backup",
        "authors": "authors_backup",
        "boxes": "boxes_backup",
        "libraries": "libraries_backup",
        "publisher": "publisher_backup",
    }

    def _backup(self, table, item_id):
        """Copy the current row into <table>_backup before overwriting it.

        Same contract as mainclass.Library.backup: these tables have no
        timestamp, so rowid order is the only chronology we have.
        """
        backup_table = self.BACKUP_TABLES[table]
        row = self.conn.execute(
            "SELECT * FROM {} WHERE id = ?".format(table), (item_id,)).fetchone()
        if row is None:
            return
        placeholders = ",".join("?" * len(row))
        self.conn.execute(
            "INSERT INTO {} VALUES ({})".format(backup_table, placeholders), tuple(row))

    def history(self, table, item_id):
        """Previous versions of a row, oldest first."""
        backup_table = self.BACKUP_TABLES[table]
        return self._query(
            "SELECT rowid AS revision, * FROM {} WHERE id = ? ORDER BY rowid".format(
                backup_table), (item_id,))

    def recent_history(self, limit=200):
        """A rough global edit log, newest first.

        Rough because the backup tables record no time: rowid is a proxy for
        'when', reliable in order but not in date.
        """
        entries = []
        for table, backup_table in self.BACKUP_TABLES.items():
            for row in self._query(
                    "SELECT rowid AS revision, * FROM {} ORDER BY rowid DESC "
                    "LIMIT ?".format(backup_table), (limit,)):
                entries.append({"table": table, **row})
        entries.sort(key=lambda e: e["revision"], reverse=True)
        return entries[:limit]

    # --------------------------------------------------------------- writing

    def add_author(self, christian_name, last_name):
        with self._write_lock:
            new_id = self._next_id("authors")
            self.conn.execute("INSERT INTO authors VALUES (?,?,?)",
                              (new_id, christian_name, last_name))
            self.conn.commit()
        self._touch("author ajouté : {} {}".format(christian_name, last_name))
        return new_id

    def update_author(self, author_id, christian_name, last_name):
        with self._write_lock:
            self._backup("authors", author_id)
            self.conn.execute(
                "UPDATE authors SET christian_name = ?, last_name = ? WHERE id = ?",
                (christian_name, last_name, author_id))
            self.conn.commit()
        self._touch("author modifié : {} {}".format(christian_name, last_name))

    def add_publisher(self, name):
        with self._write_lock:
            new_id = self._next_id("publisher")
            self.conn.execute("INSERT INTO publisher VALUES (?,?)", (new_id, name))
            self.conn.commit()
        self._touch("éditeur ajouté : {}".format(name))
        return new_id

    def update_publisher(self, publisher_id, name):
        with self._write_lock:
            self._backup("publisher", publisher_id)
            self.conn.execute("UPDATE publisher SET name = ? WHERE id = ?",
                              (name, publisher_id))
            self.conn.commit()
        self._touch("éditeur modifié : {}".format(name))

    def add_library(self, name, place, lines, columns):
        with self._write_lock:
            new_id = self._next_id("libraries")
            self.conn.execute("INSERT INTO libraries VALUES (?,?,?,?,?)",
                              (new_id, name, place, int(lines), int(columns)))
            self.conn.commit()
        self._touch("bibliothèque ajoutée : {}".format(name))
        return new_id

    def update_library(self, library_id, name, place, lines, columns):
        with self._write_lock:
            self._backup("libraries", library_id)
            self.conn.execute(
                "UPDATE libraries SET name = ?, place = ?, lines = ?, columns = ? "
                "WHERE id = ?", (name, place, int(lines), int(columns), library_id))
            self.conn.commit()
        self._touch("bibliothèque modifiée : {}".format(name))

    def add_box(self, name, library_id, line, column):
        with self._write_lock:
            new_id = self._next_id("boxes")
            self.conn.execute("INSERT INTO boxes VALUES (?,?,?,?,?)",
                              (new_id, name, int(library_id), int(line), column.upper()))
            self.conn.commit()
        self._touch("étagère ajoutée : {}".format(name))
        return new_id

    def update_box(self, box_id, name, library_id, line, column):
        with self._write_lock:
            self._backup("boxes", box_id)
            self.conn.execute(
                "UPDATE boxes SET name = ?, library = ?, line = ?, column = ? "
                "WHERE id = ?",
                (name, int(library_id), int(line), column.upper(), box_id))
            self.conn.commit()
        self._touch("étagère modifiée : {}".format(name))

    def add_book(self, title, author_kind, author_ids, publisher_id, more, box_id):
        author = encode_authors(author_kind, author_ids)
        with self._write_lock:
            new_id = self._next_id("books")
            self.conn.execute(
                "INSERT INTO books VALUES (?,?,?,?,?,?)",
                (new_id, title, author, int(publisher_id), more, int(box_id)))
            self.conn.commit()
        self._touch("livre ajouté : {}".format(title))
        return new_id

    def update_book(self, book_id, title, author_kind, author_ids, publisher_id,
                    more, box_id):
        author = encode_authors(author_kind, author_ids)
        with self._write_lock:
            self._backup("books", book_id)
            self.conn.execute(
                "UPDATE books SET name = ?, author = ?, publisher = ?, more = ?, "
                "box = ? WHERE id = ?",
                (title, author, int(publisher_id), more, int(box_id), book_id))
            self.conn.commit()
        self._touch("livre modifié : {}".format(title))

    def delete_book(self, book_id):
        """Tag a book deleted.  Rows are never removed, only marked.

        Hard deletion would break the desktop GUI, which addresses books by
        their position in the list.
        """
        with self._write_lock:
            already = self.conn.execute(
                "SELECT 1 FROM deleted_books WHERE book = ?", (book_id,)).fetchone()
            if already:
                return
            self.conn.execute("INSERT INTO deleted_books VALUES (?,?)",
                              (self._next_id("deleted_books"), book_id))
            self.conn.commit()
        book = self.book(book_id)
        self._touch("livre supprimé : {}".format(book["name"] if book else book_id))

    def restore_book(self, book_id):
        """Undo a delete.  Clears every tag, duplicates included."""
        with self._write_lock:
            self.conn.execute("DELETE FROM deleted_books WHERE book = ?", (book_id,))
            self.conn.commit()
        book = self.book(book_id)
        self._touch("livre restauré : {}".format(book["name"] if book else book_id))

    def move_books(self, book_ids, box_id):
        """Move a hand-picked set of books to one box (the CLI's mass_change)."""
        box_id = int(box_id)
        with self._write_lock:
            for book_id in book_ids:
                self._backup("books", int(book_id))
                self.conn.execute("UPDATE books SET box = ? WHERE id = ?",
                                  (box_id, int(book_id)))
            self.conn.commit()
        box = self._one("SELECT name FROM boxes WHERE id = ?", (box_id,))
        self._touch("{} livre(s) déplacé(s) vers {}".format(
            len(book_ids), box["name"] if box else box_id))
        return len(book_ids)

    def switch_boxes(self, from_box_id, to_box_id):
        """Move every book of one box into another (the CLI's switch_boxes)."""
        if int(from_box_id) == int(to_box_id):
            raise ValueError("source and destination boxes are the same")
        books = self.books_in_box(int(from_box_id))
        return self.move_books([b["id"] for b in books], to_box_id)

    def merge_authors(self, source_ids, target_id):
        """Repoint every book from source authors onto target.

        The source rows are left behind, unreferenced.  Deleting them would
        create a gap in authors.id, and the desktop GUI resolves authors by
        list position -- a gap there silently mis-credits every later book.
        Orphaned authors are flagged in the UI instead.
        """
        target_id = int(target_id)
        sources = {int(i) for i in source_ids} - {target_id}
        if not sources:
            return 0
        changed = 0
        with self._write_lock:
            for b in self.books():
                kind, ids = decode_authors(b["author"])
                if kind != "named" or not sources.intersection(ids):
                    continue
                new_ids = list(dict.fromkeys(
                    target_id if i in sources else i for i in ids))
                self._backup("books", b["id"])
                self.conn.execute("UPDATE books SET author = ? WHERE id = ?",
                                  (encode_authors("named", new_ids), b["id"]))
                changed += 1
            self.conn.commit()
        self._touch("{} auteur(s) fusionné(s), {} livre(s) mis à jour".format(
            len(sources), changed))
        return changed

    def merge_publishers(self, source_ids, target_id):
        """Same idea as merge_authors, and the same reason for not deleting."""
        target_id = int(target_id)
        sources = {int(i) for i in source_ids} - {target_id}
        if not sources:
            return 0
        with self._write_lock:
            placeholders = ",".join("?" * len(sources))
            rows = self.conn.execute(
                "SELECT id FROM books WHERE publisher IN ({})".format(placeholders),
                tuple(sources)).fetchall()
            for row in rows:
                self._backup("books", row["id"])
            self.conn.execute(
                "UPDATE books SET publisher = ? WHERE publisher IN ({})".format(
                    placeholders), (target_id, *sources))
            self.conn.commit()
        self._touch("{} éditeur(s) fusionné(s), {} livre(s) mis à jour".format(
            len(sources), len(rows)))
        return len(rows)
