# HomeLib

A personal library management application for cataloging a physical book collection. Books are organized into named libraries, which contain boxes arranged in a 2D grid (rows × columns). The app supports a PyQt5 desktop GUI, an interactive CLI, and a Flask server for syncing the database across machines.

## Requirements

- Python 3
- PyQt5
- Flask (for the server component)

## Usage

### GUI

```bash
python3 homelib.pyw
```

The main window lets you search books by title, author, publisher, box, or library, with real-time filtering. From the results you can add, edit, or delete entries. A visual grid shows how boxes are arranged on shelves in each library.

### CLI

```bash
python3 homelib.pyw --new       # Add new books interactively
python3 homelib.pyw --correct   # Edit existing entries
python3 homelib.pyw --delete    # Delete a book
```

### Utilities

```bash
# Print an alphabetical list of books in a library (author :: title)
python3 export.py <library_name>

# Count the total number of volumes (tomes) across the database
python3 volumes.py
```

## Database sync

`Library.db` is the authoritative copy on the machine named `zenon`. Client machines sync from a Flask server running on `palantir` (port 8888). The client (`dbupdater.py`) compares SHA256 checksums and only downloads when the remote copy differs.

To change the server hostname/port, edit the `server` variable at the top of `dbupdater.py`.

### Running the server automatically (on `palantir`)

```bash
sudo cp server/homelib-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now homelib-server.service
```

### Syncing automatically on client machines

```bash
sudo cp homelib-sync.service homelib-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now homelib-sync.timer
```

The timer runs 1 minute after boot and then every 30 minutes. Run `systemctl list-timers homelib-sync.timer` to check the next scheduled sync, or trigger an immediate sync with:

```bash
systemctl start homelib-sync.service
```

To see sync logs: `journalctl -u homelib-sync.service`.

## Data model

| Entity | Description |
|--------|-------------|
| Library | A named physical location with a grid of `lines × columns` |
| Box | A storage box at a `(line, column)` position within a library |
| Book | A title linked to a box, author(s), and publisher |
| Author | First and last name; a book can have multiple authors |
| Publisher | Publisher name |

Books track multiple authors via a pipe-delimited string stored in the `author` field (`count|id1|id2|...`). The special values `collective` and `anonymous` are also supported.

Every update operation backs up the previous row to a corresponding `*_backup` table before making changes.
