#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende

import hashlib
import logging
import os
import platform
import urllib.request

# logging


server = 'http://palantir:8888/'
dev_comp = 'lasna'

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

def download(server_sum):
    while not is_same_sum(server_sum,temp_lib):
        urllib.request.urlretrieve(server + 'downloader.py',temp_lib)
    os.remove(library)
    os.rename(temp_lib,library)

def updateDB():
    sum = checksum()
    if not sum or is_same_sum(sum,library) or platform.node() == dev_comp:
        return
    download(sum)




