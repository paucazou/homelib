#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende
"""Add the /homelib include to an existing nginx site, without disturbing it.

The thermometer owns port 80 on this Pi.  Rather than move it, or copy its
configuration into ours and risk the two drifting apart, we add exactly one line
to its server block:

    include snippets/homelib-location.conf;

Running this again does nothing, and the file it changes is copied to
*.before-homelib first, so the thermometer can always be put back as it was.
"""

import re
import shutil
import sys

INCLUDE = "include snippets/homelib-location.conf;"


def add(path):
    with open(path, encoding="utf-8") as handle:
        text = handle.read()

    if "homelib-location.conf" in text:
        print("thermo already serves /homelib -- nothing to do")
        return 0

    # server_name is the anchor: it sits inside the server block, above the
    # location blocks, and every Debian nginx site has one.  Inserting after the
    # first occurrence puts our include in the first (and here only) server.
    anchor = re.search(r"^[ \t]*server_name[^;]*;[ \t]*$", text, re.M)
    if anchor is None:
        print("!! no server_name found in {}.\n"
              "!! Add this line by hand inside the server block:\n"
              "!!     {}".format(path, INCLUDE), file=sys.stderr)
        return 1

    shutil.copyfile(path, path + ".before-homelib")
    indent = re.match(r"[ \t]*", anchor.group(0)).group(0) or "\t"
    insert = ("\n\n{0}# The library, on this same port under /homelib.\n"
              "{0}{1}".format(indent, INCLUDE))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text[:anchor.end()] + insert + text[anchor.end():])
    print("added the /homelib include ({}.before-homelib keeps the original)"
          .format(path))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: add_homelib_location.py /etc/nginx/sites-available/thermo",
              file=sys.stderr)
        sys.exit(2)
    sys.exit(add(sys.argv[1]))
