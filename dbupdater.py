#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende

"""Pulls a fresh Library.db down from the Pi.

Since the web application went in, the copy on palantir is the authoritative
one: it is what the phones and the browser write to, and what gets committed and
pushed every day.  This script overwrites the local database with that copy
whenever the two differ, so anything entered in the desktop GUI or the command
line while palantir was reachable will be replaced on the next start.  Enter
books in the web application, or on this machine only while the Pi is off.

The address below is unchanged on purpose: the web application listens on the
same port 8888 and answers the same two URLs, so this file did not have to move.
"""

import hashlib
import logging
import os
import platform
import urllib.request

# logging


server = 'http://palantir:8888/'
dev_comp = 'zenon'

main_dir = os.path.dirname(os.path.abspath(__file__)) + '/'
library = main_dir + 'Library.db'
temp_lib = main_dir + 'tmp/lib.db'
with open(temp_lib,'w') as file : file.write('')

def checksum():
    try:
        url = server + 'dbchecksum.py'
        return urllib.request.urlopen(url).read().decode('utf-8')
    except:
        print('Server unattainable')
        return False

def is_same_sum(server_sum,db):
    with open(db,'rb') as file:
            sum = hashlib.sha256(file.read()).hexdigest()
    if server_sum == sum:
        return True

def download(server_sum, attempts=5):
    """Fetch the database until it matches the server's checksum.

    The web application writes to that file at any moment, so a save landing
    between the checksum and the download changes the expected sum: ask for it
    again each round, and give up after a few tries rather than loop forever.
    """
    for _ in range(attempts):
        urllib.request.urlretrieve(server + 'downloader.py',temp_lib)
        if is_same_sum(server_sum,temp_lib):
            os.replace(temp_lib,library)
            return True
        server_sum = checksum()
        if not server_sum:
            return False
    print('Database kept changing during download; local copy left as it was')
    return False

def updateDB():
    sum = checksum()
    if not sum or is_same_sum(sum,library) or platform.node() == dev_comp:
        return
    download(sum)




