#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende
import hashlib
import os

from flask import Flask, redirect, url_for

app = Flask("Homelib Server")

@app.route("/dbchecksum.py")
def dbchecksum():
    db = os.path.realpath('static') + '/Library.db'
    with open(db,'rb') as file:
        sum = hashlib.sha256(file.read()).hexdigest()
    return sum

@app.route("/downloader.py")
def downloader():
    return redirect(url_for('static', filename="Library.db"))

with app.test_request_context():
    url_for('static', filename="Library.db")





