#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende

import argparse

parser = argparse.ArgumentParser("Research or enter books")
exclusive = parser.add_mutually_exclusive_group()

exclusive.add_argument("-n","--new",action="store_true",help="Enter new book titles")
exclusive.add_argument("-c","--correct",action="store_true",help="Correct items")
exclusive.add_argument("-d","--delete", action="store_true",help="Delete a book")

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
    parser.print_help()
