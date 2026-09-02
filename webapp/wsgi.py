#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende
"""WSGI entry point: gunicorn -c deploy/gunicorn.conf.py webapp.wsgi:app"""

from .app import app

__all__ = ["app"]
