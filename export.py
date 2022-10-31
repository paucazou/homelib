#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende
"""This script can export a list of books with authors
in alphabetical order from a specific library"""

import mainclass
import sys


def get_authors_strings(s,db):
    """Takes s as the string in database and return authors names"""
    if s in (db.COLLECTIVE, db.ANONYMOUS):
        return s
    ids = [int(i) for i in s.split('|')][1:]
    authors = [db.findAuthor(id) for id in ids]
    authors = [f"{elt[-1]} {elt[-2]}" for elt in authors]
    return ", ".join(authors)

db = mainclass.Library("Library.db")
# lib id
try:
    lib_name = sys.argv[1]
except:
    sys.exit("Enter an argument")
try:
    lib_id = db.findLibraryID(lib_name)
except:
    print(db.listLibraries())
    sys.exit(f"{lib_name} not found")

# boxes
boxes_ids = [ elt[0] for elt in db.listBoxes() if elt[2] == lib_id]

# books in boxes
books_infos = [book[1:3] for id in boxes_ids for book in db.booksByBox(box_id=id) ]
result = [f"{get_authors_strings(elt[1],db)} :: {elt[0]}" for elt in books_infos]
result.sort()
for elt in result:
    print(elt)





