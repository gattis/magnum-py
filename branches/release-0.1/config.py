


#### Example config file for serving django and static files ####

# import django.core.handlers.wsgi
# import magnum.http
# import magnum.http.wsgi
# import magnum.http.static
# import magnum.http.dispatch

# WORKERS = 10
# HOST = ('localhost', 80)
# HANDLER_CLASS = magnum.http.dispatch.DispatchWrapper({
#        "^/media/": magnum.http.static.StaticWrapper("/home/www/media/","/media/"),
#        "^/about/": magnum.http.static.StaticWrapper("/home/www/about_html/","/about/"),
#        "^/favicon.ico$": magnum.http.static.StaticWrapper("/home/www/media/","/"),
#        "default": magnum.http.wsgi.WSGIWrapper(django.core.handlers.wsgi.WSGIHandler())
#      })
# DEBUG = True
# PID_FILE = '/tmp/magnum.pid'
# LOG_FILE = '/var/log/magnum.out'
