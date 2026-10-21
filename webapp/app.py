#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende
"""The Homelib web application.

Everything the desktop GUI and the command line tool can do is reachable here,
plus the things neither could: restoring a deleted book, reading the edit
history that has been quietly accumulating in the *_backup tables, merging two
spellings of the same author, and finding a book from a phone while standing in
front of the shelves.

Search is deliberately not a server round-trip.  The whole catalogue goes to the
browser once, gzipped and ETag'd, and filtering happens there; a Pi Zero
answering a query per keystroke would feel broken, and the desktop app people
are used to filters in memory too.
"""

import atexit
import hashlib
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from flask import (Flask, Response, jsonify, request, send_from_directory,
                   render_template)

from . import db as dbmod
from . import volumes as volmod
from .gitsync import GitSync

log = logging.getLogger("homelib")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir))


class PrefixMiddleware:
    """Lets the same process answer at the site root and under a sub-path.

    The application is reachable two ways: http://palantir:8888/, which the
    desktop client has always used and must keep working, and
    http://palantir/homelib, served by the thermometer's nginx alongside its own
    pages.  Rather than run it twice, nginx sends "X-Forwarded-Prefix: /homelib"
    on the second one, and this moves that prefix out of PATH_INFO and into
    SCRIPT_NAME -- which is where WSGI expects the mount point, and what makes
    url_for() emit /homelib/static/app.js instead of /static/app.js.

    The header comes from our own nginx.  It is still validated, because a
    request arriving directly on 8888 could carry one too, and a prefix out of
    a stranger's hands would end up inside the URLs of every page we serve.
    """

    ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_/")

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        prefix = (environ.get("HTTP_X_FORWARDED_PREFIX") or "").rstrip("/")
        # A single leading slash: "//host" is a protocol-relative URL, and one
        # of those in SCRIPT_NAME would send every asset link off to a machine
        # of the sender's choosing.
        if prefix.startswith("/") and not prefix.startswith("//") \
                and ".." not in prefix and not set(prefix) - self.ALLOWED:
            path = environ.get("PATH_INFO", "")
            rest = path[len(prefix):] if path.startswith(prefix) else None
            # Only on a whole path segment: with prefix "/home", "/homelib/x"
            # starts with it but is not inside it.
            if rest is not None and (rest == "" or rest.startswith("/")):
                environ["PATH_INFO"] = rest or "/"
                environ["SCRIPT_NAME"] = environ.get("SCRIPT_NAME", "") + prefix
        return self.wsgi_app(environ, start_response)


class ApiError(Exception):
    """A client mistake, reported as a message the interface can show."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def create_app(config=None):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.wsgi_app = PrefixMiddleware(app.wsgi_app)
    app.config.update(
        DB_PATH=os.environ.get("HOMELIB_DB", os.path.join(REPO, "Library.db")),
        REPO_DIR=os.environ.get("HOMELIB_REPO", REPO),
        DUMP_PATH=os.environ.get("HOMELIB_DUMP", os.path.join(REPO, "Library.sql")),
        SUMS_PATH=os.environ.get("HOMELIB_SUMS", os.path.join(REPO, "sums.csv")),
        SSH_KEY=os.environ.get("HOMELIB_SSH_KEY") or None,
        GIT_REMOTE=os.environ.get("HOMELIB_GIT_REMOTE", "origin"),
        GIT_BRANCH=os.environ.get("HOMELIB_GIT_BRANCH", "master"),
        COMMIT_DEBOUNCE=int(os.environ.get("HOMELIB_DEBOUNCE", "120")),
        GIT_ENABLED=os.environ.get("HOMELIB_GIT", "1") != "0",
        JSON_SORT_KEYS=False,
    )
    if config:
        app.config.update(config)

    sync = GitSync(app.config["REPO_DIR"], app.config["DB_PATH"],
                   app.config["DUMP_PATH"], remote=app.config["GIT_REMOTE"],
                   branch=app.config["GIT_BRANCH"],
                   debounce=app.config["COMMIT_DEBOUNCE"],
                   ssh_key=app.config["SSH_KEY"])
    if app.config["GIT_ENABLED"]:
        sync.start()
        # A restart must not leave the last few books described only as
        # "modifications" in the next commit message.  The data itself is
        # already on disk either way -- this is about a readable history.
        atexit.register(sync.stop)

    _added = dbmod.ensure_schema(app.config["DB_PATH"])
    library = dbmod.Library(app.config["DB_PATH"],
                            on_write=sync.note if app.config["GIT_ENABLED"] else None)

    # Fill in any volume count that is still unknown, from the description.
    # Only NULLs are touched, so a number given by hand always stands and
    # re-running this costs nothing.
    _sums = volmod.load_sums(app.config["SUMS_PATH"])
    _filled, _left = library.backfill_volumes(lambda more: volmod.count(more, _sums))
    if _filled:
        log.info("volumes established for %d book(s), %d still unknown",
                 _filled, _left)
    # The migration changes the database, so it deserves a commit of its own
    # rather than being folded silently into whatever is edited next.
    if (_added or _filled) and app.config["GIT_ENABLED"]:
        sync.note("colonne « volumes » : {} livre(s) renseigné(s), {} à préciser"
                  .format(_filled, _left))
    app.library = library
    app.sync = sync

    # ------------------------------------------------------------- helpers

    def payload():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ApiError("Corps de requête JSON attendu")
        return data

    def need(data, key):
        value = data.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ApiError("Champ obligatoire manquant : {}".format(key))
        return value.strip() if isinstance(value, str) else value

    def need_int(data, key):
        try:
            return int(need(data, key))
        except (TypeError, ValueError):
            raise ApiError("Le champ {} doit être un nombre".format(key))

    def need_ids(data, key, message):
        """A non-empty list of integer ids.

        int() on each element used to happen unguarded, so a stray string in
        the list turned a client mistake into a 500.
        """
        ids = data.get(key) or []
        if not isinstance(ids, list) or not ids:
            raise ApiError(message)
        try:
            return [int(i) for i in ids]
        except (TypeError, ValueError):
            raise ApiError("Identifiant invalide dans {}".format(key))

    def read_authors(data):
        """Validate the three ways a book can be attributed.

        Raises ApiError, never ValueError: a blanket ValueError handler used to
        turn genuine internal faults into 400s and hid their tracebacks.
        """
        kind = data.get("author_kind", "named")
        if kind in (dbmod.ANONYMOUS, dbmod.COLLECTIVE):
            return kind, []
        if kind != "named":
            raise ApiError("Type d'auteur inconnu : {}".format(kind))
        ids = data.get("author_ids") or []
        if not isinstance(ids, list) or not ids:
            raise ApiError("Choisissez au moins un auteur, ou cochez "
                           "anonyme / collectif")
        known = {a["id"] for a in library.authors()}
        try:
            ids = [int(i) for i in ids]
        except (TypeError, ValueError):
            raise ApiError("Identifiant d'auteur invalide")
        unknown = [i for i in ids if i not in known]
        if unknown:
            raise ApiError("Auteur inconnu : {}".format(unknown[0]))
        return "named", ids


    def read_volumes(data, more):
        """An explicit count wins; otherwise read it off the description."""
        raw = data.get("volumes")
        if raw in (None, ""):
            count, sure = volmod.count(more, volmod.load_sums(app.config["SUMS_PATH"]))
            return count if sure else None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ApiError("Nombre de volumes invalide")
        if value < 1:
            raise ApiError("Un livre compte au moins un volume")
        return value

    def check_exists(table, item_id, label):
        rows = {"boxes": library.boxes, "publisher": library.publishers,
                "libraries": library.libraries, "authors": library.authors}[table]()
        if item_id not in {r["id"] for r in rows}:
            raise ApiError("{} inconnu(e) : {}".format(label, item_id))
        return item_id

    def check_box_position(library_id, line, column):
        lib = next((l for l in library.libraries() if l["id"] == library_id), None)
        if lib is None:
            raise ApiError("Bibliothèque inconnue : {}".format(library_id))
        if not (1 <= line <= (lib["lines"] or 0)):
            raise ApiError("Ligne {} hors de « {} » (1 à {})".format(
                line, lib["name"], lib["lines"]))
        # A membership test on the string would be a substring search, letting
        # "" and "AB" through -- and a shelf whose column is neither a letter
        # nor within the grid has no cell to be drawn in, so it vanishes.
        column = (column or "").upper()
        allowed = dbmod.ALPHABET[:lib["columns"] or 0]
        if len(column) != 1 or column not in list(allowed):
            raise ApiError("Colonne {} hors de « {} » (A à {})".format(
                column or "?", lib["name"],
                dbmod.ALPHABET[(lib["columns"] or 1) - 1]))
        return column

    def catalog_etag():
        """Cheap fingerprint of the database file, for conditional GETs."""
        try:
            st = os.stat(app.config["DB_PATH"])
        except OSError:
            return None
        return hashlib.md5(
            "{}-{}".format(st.st_mtime_ns, st.st_size).encode()).hexdigest()

    @app.errorhandler(ApiError)
    def _api_error(exc):
        return jsonify({"error": exc.message}), exc.status

    @app.errorhandler(500)
    def _server_error(exc):
        log.exception("unhandled error")
        return jsonify({"error": "Erreur interne du serveur"}), 500

    # ---------------------------------------------------------------- pages

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/manifest.webmanifest")
    def manifest():
        return send_from_directory(app.static_folder, "manifest.webmanifest",
                                   mimetype="application/manifest+json")

    @app.route("/sw.js")
    def service_worker():
        # Must be served from the application root, or its scope would be
        # limited to /static/ and it could not cache the pages themselves.
        response = send_from_directory(app.static_folder, "sw.js",
                                       mimetype="application/javascript")
        response.headers["Cache-Control"] = "no-cache"
        return response

    # ------------------------------------------------------------- catalogue

    # Building the catalogue means reading every table and encoding 1.2 MB of
    # JSON.  That is 20 ms on a laptop and well over a second on the Pi Zero
    # this runs on, so both the structure and the encoded bytes are kept until
    # the database file changes.  Statistics and exports read the same copy --
    # rebuilding it per page was most of what made those pages slow.
    _catalog_cache = {"etag": None, "data": None, "body": None}
    _catalog_lock = threading.Lock()

    def cached_catalog():
        """Returns (etag, data, encoded_body), building only when stale."""
        etag = catalog_etag()
        with _catalog_lock:
            if not etag or _catalog_cache["etag"] != etag:
                data = library.catalog()          # includes the usage counts
                data["version"] = etag
                _catalog_cache["data"] = data
                _catalog_cache["body"] = json.dumps(
                    data, ensure_ascii=False).encode("utf-8")
                _catalog_cache["etag"] = etag
            return etag, _catalog_cache["data"], _catalog_cache["body"]

    @app.route("/api/catalog")
    def api_catalog():
        # set_etag / if_none_match rather than a raw header: nginx weakens an
        # ETag to W/"..." when it gzips a response, and drops an unquoted one
        # altogether -- which it was doing, so no browser ever revalidated and
        # the whole catalogue came down again on every single page load.
        current = catalog_etag()
        if current and request.if_none_match.contains_weak(current):
            return Response(status=304)
        etag, _, body = cached_catalog()
        response = Response(body, mimetype="application/json")
        if etag:
            response.set_etag(etag)
            # Always revalidate: the catalogue changes the moment a book is
            # saved, and a stale shelf number is worse than a quick check.
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

    # ------------------------------------------------------------------ books

    @app.route("/api/books", methods=["POST"])
    def api_add_book():
        data = payload()
        kind, ids = read_authors(data)
        more = (data.get("more") or "").strip()
        book_id = library.add_book(
            need(data, "title"), kind, ids,
            check_exists("publisher", need_int(data, "publisher_id"), "Éditeur"),
            more,
            check_exists("boxes", need_int(data, "box_id"), "Étagère"),
            read_volumes(data, more))
        return jsonify({"id": book_id}), 201

    @app.route("/api/books/<int:book_id>", methods=["PUT"])
    def api_update_book(book_id):
        if library.book(book_id) is None:
            raise ApiError("Livre inconnu", 404)
        data = payload()
        kind, ids = read_authors(data)
        more = (data.get("more") or "").strip()
        library.update_book(
            book_id, need(data, "title"), kind, ids,
            check_exists("publisher", need_int(data, "publisher_id"), "Éditeur"),
            more,
            check_exists("boxes", need_int(data, "box_id"), "Étagère"),
            read_volumes(data, more))
        return jsonify({"id": book_id})

    @app.route("/api/books/<int:book_id>", methods=["DELETE"])
    def api_delete_book(book_id):
        if library.book(book_id) is None:
            raise ApiError("Livre inconnu", 404)
        library.delete_book(book_id)
        return jsonify({"id": book_id, "deleted": True})

    @app.route("/api/books/<int:book_id>/restore", methods=["POST"])
    def api_restore_book(book_id):
        if library.book(book_id) is None:
            raise ApiError("Livre inconnu", 404)
        library.restore_book(book_id)
        return jsonify({"id": book_id, "deleted": False})

    @app.route("/api/books/move", methods=["POST"])
    def api_move_books():
        """The command line's 'Boxes: mass' -- move chosen books to one box."""
        data = payload()
        ids = need_ids(data, "book_ids", "Sélectionnez au moins un livre")
        known = {b["id"] for b in library.books()}
        unknown = [i for i in ids if i not in known]
        if unknown:
            raise ApiError("Livre inconnu : {}".format(unknown[0]))
        box_id = check_exists("boxes", need_int(data, "box_id"), "Étagère")
        return jsonify({"moved": library.move_books(ids, box_id)})

    # ------------------------------------------------------------------ boxes

    @app.route("/api/boxes", methods=["POST"])
    def api_add_box():
        data = payload()
        library_id = check_exists("libraries", need_int(data, "library_id"),
                                  "Bibliothèque")
        line = need_int(data, "line")
        column = check_box_position(library_id, line, data.get("column"))
        return jsonify({"id": library.add_box(need(data, "name"), library_id,
                                              line, column)}), 201

    @app.route("/api/boxes/<int:box_id>", methods=["PUT"])
    def api_update_box(box_id):
        # Without this an UPDATE that matches nothing still answers 200, the
        # interface says "Enregistré", and a git commit is queued for a change
        # that was never made.
        check_exists("boxes", box_id, "Étagère")
        data = payload()
        library_id = check_exists("libraries", need_int(data, "library_id"),
                                  "Bibliothèque")
        line = need_int(data, "line")
        column = check_box_position(library_id, line, data.get("column"))
        library.update_box(box_id, need(data, "name"), library_id, line, column)
        return jsonify({"id": box_id})

    @app.route("/api/boxes/switch", methods=["POST"])
    def api_switch_boxes():
        """The command line's 'Switch boxes' -- empty one shelf into another."""
        data = payload()
        source = check_exists("boxes", need_int(data, "from_box_id"), "Étagère")
        target = check_exists("boxes", need_int(data, "to_box_id"), "Étagère")
        if source == target:
            raise ApiError("Les deux étagères sont identiques")
        return jsonify({"moved": library.switch_boxes(source, target)})

    # -------------------------------------------------------------- libraries

    @app.route("/api/libraries", methods=["POST"])
    def api_add_library():
        data = payload()
        lines, columns = need_int(data, "lines"), need_int(data, "columns")
        if not 1 <= lines <= 99 or not 1 <= columns <= 26:
            raise ApiError("Dimensions invalides (lignes 1-99, colonnes 1-26)")
        return jsonify({"id": library.add_library(
            need(data, "name"), need(data, "place"), lines, columns)}), 201

    @app.route("/api/libraries/<int:library_id>", methods=["PUT"])
    def api_update_library(library_id):
        check_exists("libraries", library_id, "Bibliothèque")
        data = payload()
        lines, columns = need_int(data, "lines"), need_int(data, "columns")
        if not 1 <= lines <= 99 or not 1 <= columns <= 26:
            raise ApiError("Dimensions invalides (lignes 1-99, colonnes 1-26)")
        # Shrinking a library would strand the shelves outside the new grid.
        def outside(box):
            if box["line"] > lines:
                return True
            try:
                return dbmod.column_index(box["column"]) >= columns
            except ValueError:
                # A column that is not a letter is already unplaceable; block
                # the resize rather than crash on it.
                return True

        stranded = [b for b in library.boxes()
                    if b["library"] == library_id and outside(b)]
        if stranded:
            raise ApiError(
                "Impossible de réduire : {} étagère(s) se retrouveraient hors "
                "de la grille ({}).".format(
                    len(stranded), ", ".join(b["name"] for b in stranded[:5])))
        library.update_library(library_id, need(data, "name"),
                               need(data, "place"), lines, columns)
        return jsonify({"id": library_id})

    # ---------------------------------------------------------------- authors

    @app.route("/api/authors", methods=["POST"])
    def api_add_author():
        data = payload()
        first = (data.get("christian_name") or "").strip()
        last = (data.get("last_name") or "").strip()
        if not first and not last:
            raise ApiError("Indiquez au moins un nom")
        return jsonify({"id": library.add_author(first, last)}), 201

    @app.route("/api/authors/<int:author_id>", methods=["PUT"])
    def api_update_author(author_id):
        check_exists("authors", author_id, "Auteur")
        data = payload()
        first = (data.get("christian_name") or "").strip()
        last = (data.get("last_name") or "").strip()
        if not first and not last:
            raise ApiError("Indiquez au moins un nom")
        library.update_author(author_id, first, last)
        return jsonify({"id": author_id})

    @app.route("/api/authors/merge", methods=["POST"])
    def api_merge_authors():
        data = payload()
        target = check_exists("authors", need_int(data, "target_id"), "Auteur")
        sources = [check_exists("authors", i, "Auteur") for i in need_ids(
            data, "source_ids", "Sélectionnez les auteurs à fusionner")]
        return jsonify({"updated": library.merge_authors(sources, target)})

    # ------------------------------------------------------------- publishers

    @app.route("/api/publishers", methods=["POST"])
    def api_add_publisher():
        return jsonify({"id": library.add_publisher(need(payload(), "name"))}), 201

    @app.route("/api/publishers/<int:publisher_id>", methods=["PUT"])
    def api_update_publisher(publisher_id):
        check_exists("publisher", publisher_id, "Éditeur")
        library.update_publisher(publisher_id, need(payload(), "name"))
        return jsonify({"id": publisher_id})

    @app.route("/api/publishers/merge", methods=["POST"])
    def api_merge_publishers():
        data = payload()
        target = check_exists("publisher", need_int(data, "target_id"), "Éditeur")
        sources = [check_exists("publisher", i, "Éditeur") for i in need_ids(
            data, "source_ids", "Sélectionnez les éditeurs à fusionner")]
        return jsonify({"updated": library.merge_publishers(sources, target)})

    # ---------------------------------------------------------------- history

    @app.route("/api/history/<table>/<int:item_id>")
    def api_history(table, item_id):
        if table not in dbmod.Library.BACKUP_TABLES:
            raise ApiError("Table inconnue : {}".format(table), 404)
        return jsonify({"table": table, "id": item_id,
                        "revisions": library.history(table, item_id)})

    @app.route("/api/history")
    def api_recent_history():
        # At least one: SQLite reads LIMIT -1 as "no limit", and a negative
        # limit also made recent_history stop after its first entry.
        try:
            limit = max(1, min(int(request.args.get("limit", 100)), 500))
        except ValueError:
            raise ApiError("Paramètre limit invalide")
        return jsonify({"entries": library.recent_history(limit)})

    # ------------------------------------------------------------------ stats

    @app.route("/api/stats")
    def api_stats():
        catalog = cached_catalog()[1]
        books = catalog["books"]
        active = [b for b in books if not b["deleted"]]
        # The stored column is the authority now; a book without one counts as
        # a single volume and is listed for someone to confirm.
        total_volumes = sum(b["volumes"] or 1 for b in active)
        unknown = [b for b in active if b["volumes"] is None]

        by_library, by_box, by_author, by_publisher = {}, {}, {}, {}
        for b in active:
            by_library[b["library"]] = by_library.get(b["library"], 0) + 1
            by_box[b["box"]] = by_box.get(b["box"], 0) + 1
            by_publisher[b["publisher"]] = by_publisher.get(b["publisher"], 0) + 1
            for name in b["authors"]:
                by_author[name] = by_author.get(name, 0) + 1

        top = lambda d, n=15: sorted(
            ({"name": k or "—", "count": v} for k, v in d.items()),
            key=lambda x: (-x["count"], x["name"]))[:n]

        return jsonify({
            "totals": {
                "books": len(active),
                "deleted": len(books) - len(active),
                "volumes": total_volumes,
                "authors": len(catalog["authors"]),
                "publishers": len(catalog["publishers"]),
                "boxes": len(catalog["boxes"]),
                "libraries": len(catalog["libraries"]),
            },
            "by_library": top(by_library, 50),
            "by_box": top(by_box, 25),
            "by_author": top(by_author),
            "by_publisher": top(by_publisher),
            "unresolved_volumes": [
                {"id": b["id"], "title": b["title"], "text": b["more"]}
                for b in unknown],
        })

    @app.route("/api/volumes/resolve", methods=["POST"])
    def api_resolve_volumes():
        """Record how many volumes a book amounts to.

        The answer goes into the book's own column, and -- when the count was
        read off a description -- into sums.csv as well, keyed by the same md5
        the desktop volumes.py uses, so it is only ever asked once.
        """
        data = payload()
        if data.get("book_ids") is None and data.get("book_id") is not None:
            data["book_ids"] = [data["book_id"]]
        ids = need_ids(data, "book_ids", "Aucun livre indiqué")
        try:
            n = int(need(data, "count"))
        except (TypeError, ValueError):
            raise ApiError("Nombre de volumes invalide")
        if n < 1:
            raise ApiError("Un livre compte au moins un volume")

        known = {b["id"] for b in library.books()}
        unknown = [i for i in ids if i not in known]
        if unknown:
            raise ApiError("Livre inconnu : {}".format(unknown[0]))

        library.set_volumes(ids, n)
        text = data.get("text")
        if text:
            volmod.record_sum(app.config["SUMS_PATH"], volmod.text_hash(text), n)
        return jsonify({"books": len(ids), "count": n})

    # ----------------------------------------------------------------- export

    @app.route("/api/export")
    def api_export():
        """Generalises export.py: author :: title, alphabetically, per library."""
        catalog = cached_catalog()[1]
        books = [b for b in catalog["books"] if not b["deleted"]]
        wanted = request.args.get("library")
        if wanted and wanted != "all":
            books = [b for b in books if str(b["library_id"]) == str(wanted)]
        include_deleted = request.args.get("deleted") == "1"
        if include_deleted:
            books = [b for b in catalog["books"]
                     if not wanted or wanted == "all"
                     or str(b["library_id"]) == str(wanted)]

        def author_string(book):
            if book["author_kind"] == dbmod.ANONYMOUS:
                return "anonymous"
            if book["author_kind"] == dbmod.COLLECTIVE:
                return "collective"
            return ", ".join(book["authors"])

        fmt = request.args.get("format", "txt")
        stamp = time.strftime("%Y%m%d")
        if fmt == "json":
            return Response(
                json.dumps(books, ensure_ascii=False, indent=1),
                mimetype="application/json",
                headers={"Content-Disposition":
                         'attachment; filename="homelib-{}.json"'.format(stamp)})
        if fmt == "csv":
            import csv as csvmod
            import io
            buf = io.StringIO()
            writer = csvmod.writer(buf)
            writer.writerow(["Titre", "Auteurs", "Éditeur", "Étagère",
                             "Emplacement", "Bibliothèque", "Détails", "Supprimé"])
            for b in sorted(books, key=lambda x: (author_string(x).lower(),
                                                  x["title"].lower())):
                writer.writerow([b["title"], author_string(b), b["publisher"],
                                 b["box"], b["box_ref"], b["library"],
                                 b["more"], "oui" if b["deleted"] else ""])
            return Response(
                "﻿" + buf.getvalue(),  # BOM so Excel reads the accents
                mimetype="text/csv; charset=utf-8",
                headers={"Content-Disposition":
                         'attachment; filename="homelib-{}.csv"'.format(stamp)})

        lines = sorted("{} :: {}".format(author_string(b), b["title"])
                       for b in books)
        return Response("\n".join(lines) + "\n", mimetype="text/plain; charset=utf-8")

    # ------------------------------------------------------------------- ISBN

    _isbn_cache = {}
    _isbn_lock = threading.Lock()

    @app.route("/api/isbn/<isbn>")
    def api_isbn(isbn):
        """Look a book up by ISBN to pre-fill the form.

        Proxied through the server rather than fetched by the browser: it keeps
        the lookup working when the page is served over plain http, and lets one
        cache serve every device in the house.
        """
        isbn = "".join(c for c in isbn if c.isalnum()).upper()
        if len(isbn) not in (10, 13):
            raise ApiError("Un ISBN compte 10 ou 13 caractères")
        with _isbn_lock:
            if isbn in _isbn_cache:
                return jsonify(_isbn_cache[isbn])

        url = ("https://openlibrary.org/api/books?bibkeys=ISBN:{}"
               "&format=json&jscmd=data".format(urllib.parse.quote(isbn)))
        try:
            with urllib.request.urlopen(url, timeout=12) as response:
                found = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            raise ApiError("Recherche ISBN indisponible ({})".format(exc), 503)

        entry = found.get("ISBN:{}".format(isbn))
        if not entry:
            raise ApiError("Aucun livre trouvé pour l'ISBN {}".format(isbn), 404)

        result = {
            "isbn": isbn,
            "title": entry.get("title", ""),
            "subtitle": entry.get("subtitle", ""),
            "authors": [a.get("name", "") for a in entry.get("authors", [])],
            "publishers": [p.get("name", "") for p in entry.get("publishers", [])],
            "date": entry.get("publish_date", ""),
            "pages": entry.get("number_of_pages"),
        }
        with _isbn_lock:
            _isbn_cache[isbn] = result
        return jsonify(result)

    # ------------------------------------------------------------- git status

    @app.route("/api/sync")
    def api_sync_status():
        if not app.config["GIT_ENABLED"]:
            return jsonify({"enabled": False})
        return jsonify({"enabled": True, **sync.status()})

    @app.route("/api/sync", methods=["POST"])
    def api_sync_now():
        """Commit anything pending and push, on demand.

        The timer does this daily; the button is for when you want to know the
        additions are safely off the Pi before closing the laptop.
        """
        if not app.config["GIT_ENABLED"]:
            raise ApiError("La synchronisation git est désactivée", 409)
        result = sync.push()
        return jsonify({**result, **sync.status()})

    # ------------------------------------------- compatibility with dbupdater

    @app.route("/dbchecksum.py")
    def dbchecksum():
        """Kept for the desktop client: dbupdater.py polls this to decide
        whether its copy of Library.db is stale."""
        with open(app.config["DB_PATH"], "rb") as f:
            return Response(hashlib.sha256(f.read()).hexdigest(),
                            mimetype="text/plain")

    @app.route("/downloader.py")
    def downloader():
        """Kept for the desktop client: hands over the database file itself."""
        directory, name = os.path.split(app.config["DB_PATH"])
        return send_from_directory(directory, name, as_attachment=True,
                                   download_name="Library.db")

    @app.route("/healthz")
    def healthz():
        return jsonify({"ok": True, "books": len(library.books())})

    return app


app = create_app()
