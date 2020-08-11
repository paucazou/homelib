#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende

import argparse
import os
import sys

parser = argparse.ArgumentParser("Research or enter books")
exclusive = parser.add_mutually_exclusive_group()

exclusive.add_argument("-n","--new",action="store_true",help="Enter new book titles")
exclusive.add_argument("-c","--correct",action="store_true",help="Correct items")
exclusive.add_argument("-d","--delete", action="store_true",help="Delete a book")
exclusive.add_argument("-g","--gui",action="store_true",help="Open Graphical User Interface")

args = parser.parse_args()

if args.new or args.correct or args.delete:
    import clfun
    if args.new:
        clfun.goon(clfun.newBook)
    elif args.correct:
        clfun.goon(clfun.correct)
    elif args.delete:
        clfun.delete_book()
    del(clfun.library)
else:
    from gui import mainwindow
    db_path = os.path.dirname(os.path.abspath(__file__)) + '/Library.db'
    app = mainwindow.GuiApp([db_path])
    sys.exit(app.exec_())
