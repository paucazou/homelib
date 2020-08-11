#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende

import cgi
import os
import shutil
import sys

print('Content-Type: application/octet-stream; file="Library.db"')
print('Content-Disposition: attachment; filename="Library.db"\n')

sys.stdout.flush()
db = os.path.realpath('..') + '/Library.db'
with open(db,'rb') as file:
    shutil.copyfileobj(file, sys.stdout.buffer)
