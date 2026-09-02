#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende
"""Counting physical volumes from a book's free-text 'more' field.

A port of the top-level volumes.py.  The logic is the same -- look for a number
in front of the words 'tomes' or 'volumes', understanding French numerals --
with one difference: the original stops and asks the operator at the prompt when
it cannot tell.  A web request cannot do that, so an unresolved entry is
reported back with its hash and the interface asks the user later, writing the
answer into the same sums.csv the desktop script already consults.
"""

import csv
import hashlib
import os
import re
import threading

# Values of the individual French number words.  'vingt' and 'cent' are
# multipliers as well as values, so they get special treatment in to_int.
FRENCH_NUMBERS = {
    "zéro": 0, "zero": 0, "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4,
    "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11,
    "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16,
    "vingt": 20, "vingts": 20, "trente": 30, "quarante": 40, "cinquante": 50,
    "soixante": 60, "cent": 100, "cents": 100, "mille": 1000, "milles": 1000,
    "premier": 1, "première": 1, "second": 2, "seconde": 2,
}

_lock = threading.Lock()

# Longest French number phrase we will read back from before "tomes",
# e.g. "quatre-vingt-dix mille deux cent trois".
MAX_NUMBER_WORDS = 6


def to_int(number):
    """Parse an int, an Arabic numeral, or a French number phrase.

    The top-level volumes.py splits French numbers on 'et' and '-' and adds the
    halves together, which is right for "soixante et onze" (71) but wrong for
    "quatre-vingt-dix": 4 + 20 + 10 = 34 rather than 90.  French multiplies
    'vingt' by a preceding 'quatre' and 'cent' by whatever precedes it, so we
    accumulate with those two rules instead of summing blindly.
    """
    if isinstance(number, int):
        return number
    try:
        return int(number)
    except (TypeError, ValueError):
        pass
    if not isinstance(number, str):
        raise ValueError("Invalid input: {}".format(number))

    words = [w for w in re.split(r"[\s-]+", number.lower().strip()) if w]
    if not words:
        raise ValueError("Invalid input: {}".format(number))

    total = 0
    current = 0
    seen = False
    for word in words:
        if word == "et":  # the joining 'et' of "vingt et un" carries no value
            continue
        if word.isdigit():
            current += int(word)
            seen = True
            continue
        if word not in FRENCH_NUMBERS:
            raise ValueError("Invalid input: {}".format(number))
        seen = True
        value = FRENCH_NUMBERS[word]
        if value == 1000:
            total += (current or 1) * 1000
            current = 0
        elif value == 100:
            current = (current or 1) * 100
        elif value == 20 and current == 4:
            # "quatre-vingt(s)" is the one place French multiplies by twenty.
            current = 80
        else:
            current += value

    if not seen:
        raise ValueError("Invalid input: {}".format(number))
    return total + current


def text_hash(text):
    """The key used in sums.csv: md5 of the raw 'more' field, as in volumes.py."""
    return hashlib.md5((text or "").encode()).hexdigest()


def load_sums(path):
    """Read the manual answers file.  Missing or malformed rows are skipped."""
    sums = {}
    if not os.path.exists(path):
        return sums
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if len(row) >= 2:
                try:
                    sums[row[0]] = int(row[1])
                except ValueError:
                    continue
    return sums


def record_sum(path, digest, count):
    """Append a manual answer, so neither this app nor volumes.py asks again."""
    with _lock:
        with open(path, "a", newline="") as f:
            csv.writer(f, quoting=csv.QUOTE_MINIMAL).writerow([digest, int(count)])


def count(text, sums=None):
    """Return (volumes, resolved).

    resolved is False when the text mentions volumes but we could not read a
    number from it -- the caller should ask a human.  A book with no mention at
    all is one volume, and that counts as resolved: there is nothing to ask.
    """
    raw = text or ""
    normalised = re.sub(r"[\n]", " ", re.sub(r"[.]", "", raw.lower()))
    if "volume" not in normalised and "tome" not in normalised:
        return 1, True

    total = 0
    words = normalised.split()
    for i, word in enumerate(words):
        if word not in ("volumes", "tomes") or i == 0:
            continue
        # A French number can run to several words ("vingt et un tomes"), so
        # try the longest phrase ending just before the keyword and fall back
        # to shorter ones.  Reading only the previous word, as volumes.py does,
        # turns "vingt et un tomes" into one volume.
        for length in range(min(MAX_NUMBER_WORDS, i), 0, -1):
            try:
                total += to_int(" ".join(words[i - length:i]))
            except ValueError:
                continue
            break

    if total:
        return total, True

    # Fall back to the answers a human has already given.
    manual = (sums or {}).get(text_hash(raw))
    if manual:
        return manual, True
    return 1, False


def count_books(books, sums):
    """Total volumes across books, plus whatever still needs a human.

    ``books`` are catalog entries; deleted ones are left out, since the point of
    the number is how many physical volumes are on the shelves.
    """
    total = 0
    unresolved = {}
    for book in books:
        if book.get("deleted"):
            continue
        n, resolved = count(book.get("more", ""), sums)
        total += n
        if not resolved:
            digest = text_hash(book.get("more", ""))
            entry = unresolved.setdefault(
                digest, {"hash": digest, "text": book.get("more", ""), "books": []})
            entry["books"].append({"id": book["id"], "title": book["title"]})
    return total, list(unresolved.values())
