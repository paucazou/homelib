#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende
import cgi
import hashlib
import os

db = os.path.realpath('..') + '/Library.db'


with open(db,'rb') as file:
    sum = hashlib.sha256(file.read()).hexdigest()

print("""Content-type: text/plain; charset=utf-8\n""")
print(sum,end='')
