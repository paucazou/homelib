# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HomeLib is a personal library management application for cataloging and organizing a physical book collection. It supports multiple interfaces: a PyQt5 desktop GUI, a CLI for headless/terminal use, and a Flask web server for remote database synchronization.

## Running the Application

```bash
# Launch the GUI
python3 homelib.pyw
python3 homelib.pyw --gui

# CLI modes
python3 homelib.pyw --new       # Add new books interactively
python3 homelib.pyw --correct   # Edit existing entries
python3 homelib.pyw --delete    # Delete books

# Utilities
python3 export.py [library_name]   # Export library contents
python3 volumes.py                 # Count total volumes in database
```

There are no automated tests, no build step, and no package manager. Dependencies (PyQt5, Flask) must be installed in the Python environment.

## Architecture

**`mainclass.py`** — Core `Library` class: the single database abstraction layer for all SQLite operations. Every other module imports this. CRUD methods auto-generate IDs via `_newID()` and call `backup(id, table)` before every update, writing to `{table}_backup` tables to enable undo.

**`homelib.pyw`** — Entry point. Dispatches to GUI (`gui/mainwindow.py`) or CLI (`clfun.py`) based on command-line arguments.

**`gui/`** — PyQt5 frontend:
- `mainwindow.py` — Search interface, results display, library grid visualization
- `newbook.py` — Add/edit book dialog with author/publisher autocomplete
- `libpattern.py` — 2D grid rendering of library shelves (lines × columns)
- `translation.py` — Runtime i18n via `SuperTranslator` base class; French translations in `i18n/`

**`clfun.py`** — Interactive terminal interface using readline.

**`dbupdater.py`** — Syncs `Library.db` from a remote Flask server by comparing SHA256 checksums. Skips update on the machine named `zenon` (considered the authoritative source).

**`server/server.py`** — Minimal Flask server exposing the database file for remote sync.

## Database Schema

SQLite3 database at `Library.db`. Key relationships:

- `books` → `authors` (pipe-delimited ID string: `"count|id1|id2|..."`)
- `books` → `boxes` → `libraries`
- `books` → `publishers`
- `deleted_books` — soft-delete tracking
- `*_backup` tables — backup rows before every update

Libraries have a 2D spatial grid (`lines` × `columns`) and boxes are positioned by `(line, column)` within a library.

## Internationalization

All GUI widgets inherit from `SuperTranslator` (in `gui/translation.py`). French translations are in `gui/i18n/`. To add a new language, add a `.ts` file and compile to `.qm` with `lrelease`.
