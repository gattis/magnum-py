


#### Example config file for serving django and static files ####

import django.core.handlers.wsgi
import magnum.http
import magnum.http.wsgi
import magnum.http.static
import magnum.http.dispatch

WORKERS = 10
HOST = ('mattgattis.com', 8080)
HANDLER_CLASS = magnum.http.dispatch.DispatchWrapper({
        "^/media/": magnum.http.static.StaticWrapper("/var/www/matt/media/","/media/"),
        "^/about/": magnum.http.static.StaticWrapper("/var/www/matt/about/","/about/"),
        "^/favicon.ico$": magnum.http.static.StaticWrapper("/var/www/matt/media/","/"),
        "default": magnum.http.wsgi.WSGIWrapper(django.core.handlers.wsgi.WSGIHandler())
      })
DEBUG = True
PID_FILE = '/tmp/magnum-dev.pid'
LOG_FILE = '/var/log/magnum-dev.out'
