#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende
import hashlib
import os

from flask import Flask, send_file

app = Flask("Homelib Server")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Library.db')
DB_PATH = os.path.realpath(DB_PATH)


@app.route("/dbchecksum.py")
def dbchecksum():
    if not os.path.exists(DB_PATH):
        return "Database not found", 404
    with open(DB_PATH, 'rb') as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    return digest


@app.route("/downloader.py")
def downloader():
    if not os.path.exists(DB_PATH):
        return "Database not found", 404
    return send_file(DB_PATH, mimetype='application/octet-stream',
                     as_attachment=True, download_name='Library.db')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888)
