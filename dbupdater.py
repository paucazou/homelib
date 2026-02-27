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

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

server = 'http://palantir:8888/'
dev_comp = 'zenon'
TIMEOUT = 10       # seconds for each HTTP request
MAX_RETRIES = 3    # maximum download attempts before giving up

main_dir = os.path.dirname(os.path.abspath(__file__)) + '/'
library = main_dir + 'Library.db'
temp_lib = main_dir + 'tmp/lib.db'


def checksum():
    try:
        url = server + 'dbchecksum.py'
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            return response.read().decode('utf-8').strip()
    except Exception as e:
        log.warning('Server unreachable: %s', e)
        return None


def file_checksum(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def is_same_sum(server_sum, db):
    return server_sum == file_checksum(db)


def download(server_sum):
    url = server + 'downloader.py'
    for attempt in range(1, MAX_RETRIES + 1):
        log.info('Downloading database (attempt %d/%d)…', attempt, MAX_RETRIES)
        try:
            urllib.request.urlretrieve(url, temp_lib)
        except Exception as e:
            log.warning('Download failed: %s', e)
            continue
        if is_same_sum(server_sum, temp_lib):
            os.replace(temp_lib, library)
            log.info('Database updated successfully.')
            return
        log.warning('Checksum mismatch after download, retrying…')
    log.error('Failed to download a valid database after %d attempts.', MAX_RETRIES)


def updateDB():
    if platform.node() == dev_comp:
        log.debug('Running on dev machine (%s), skipping sync.', dev_comp)
        return
    server_sum = checksum()
    if not server_sum:
        return
    if is_same_sum(server_sum, library):
        log.debug('Database already up to date.')
        return
    os.makedirs(os.path.dirname(temp_lib), exist_ok=True)
    download(server_sum)


if __name__ == '__main__':
    updateDB()
