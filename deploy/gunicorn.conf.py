# Homelib -- gunicorn settings for the Raspberry Pi it runs on.
#
# That Pi is a Zero: one armv6 core and 426 MB of memory shared with nginx,
# MySQL and PHP.  So: one worker, a few threads to keep a slow client from
# blocking the others, and no request recycling (it would throw away the
# catalogue cache, which is the single thing that keeps the app feeling quick).

bind = "127.0.0.1:8001"
workers = 1
threads = 4
worker_class = "gthread"

# preload_app would import the application in the master and fork, and threads
# do not survive a fork -- the background committer would silently never run.
preload_app = False

timeout = 120
graceful_timeout = 30
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = "info"
