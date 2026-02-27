# Known Critical Bugs

Bugs 1–5 have been fixed. Bug 6 (no auth on sync server) is a known accepted risk.

---

## Data loss — silent (edits discarded without error)

### `gui/newbook.py` — update dialogs never call update methods
All four sub-dialogs (Author, Publisher, Box, Library) have an `update` mode but their `saveData()` only calls the `add*()` method. When editing an existing record the change is silently thrown away.

| Dialog | Missing call |
|--------|-------------|
| `NewAuthorWindow.saveData()` | `db.updateAuthor()` |
| `NewPublisherWindow.saveData()` | `db.updatePublisher()` |
| `NewBoxWindow.saveData()` | `db.updateBox()` |
| `NewLibWindow.saveData()` | `db.updateLibrary()` |

---

## Crashes — ID/index lookup on missing records

### `mainclass.py` — `fetchone()[0]` without None check (lines 76, 80, 84, 88, 92, 96)
`findAuthorID`, `findBoxID`, `findBoxName`, `findLibraryID`, `findLibraryName`, `findPublisherID` all do `.fetchone()[0]` with no check for `None`. Any lookup of a non-existent record raises `TypeError: 'NoneType' object is not subscriptable`.

### `gui/mainwindow.py` — index arithmetic on IDs (lines 122–123, 207, 209)
Book and box display code uses `results['boxes'][book[-1]-1]` and `results['libraries'][box[2]-1]`, treating database IDs as zero-based list indices. If IDs have gaps (after deletions) or are out of sequence, this produces wrong data or an `IndexError`.

### `clfun.py` — author list indexed by database ID (line 42)
`list_authors[nb]` where `nb = int(id) - 1`. Same ID-as-index assumption as above.

---

## Crashes — uninitialized variable

### `volumes.py` — `hashval` used outside its `try` block (around line 80)
`hashval` is assigned inside a `try` block. If an exception is raised before that assignment and execution continues past the `except`, a later use of `hashval` raises `NameError`.

---

## Crashes — import-time file creation (fixed in dbupdater.py, noted for reference)
The original `dbupdater.py` created `tmp/lib.db` at import time with `open(temp_lib,'w')`. If `tmp/` did not exist this raised `FileNotFoundError` before any function was called. Fixed: creation is now deferred to `updateDB()` with `os.makedirs(..., exist_ok=True)`.

---

## Crashes — export on missing data

### `export.py` line 16 — `findAuthor()` returning `None`
`[elt[-1] for elt in authors]` where `authors` may contain `None` entries if an author ID stored in a book row no longer exists in the `authors` table. Raises `TypeError`.

---

## Security

### `server/server.py` — no authentication
The server binds to `0.0.0.0:8888` and serves the full database to any host that can reach it. Anyone on the same network can download `Library.db` without credentials.
