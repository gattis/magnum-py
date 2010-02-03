#### Example config file for serving django and static files ####

# import django.core.handlers.wsgi
# import magnum.http
# import magnum.http.wsgi
# import magnum.http.static
# import magnum.http.dispatch

# WORKER_PROCESSES = 8
# WORKER_THREADS_PER_PROCESS = 20
# HOST = ('localhost', 80)
# HANDLER_CLASS = magnum.http.dispatch.HostDispatchWrapper(
#     {"domainname.com": magnum.http.dispatch.PathDispatchWrapper({
#                "^/media/": magnum.http.static.StaticWrapper("/home/www/media/","/media/"),
#                "^/favicon.ico$": magnum.http.static.StaticWrapper("/home/www/media/","/"),
#                "default": magnum.http.wsgi.WSGIWrapper(django.core.handlers.wsgi.WSGIHandler())
#                }),
#     "default": magnum.http.dispatch.RedirectWrapper("http://domainname.com/")})
# DEBUG = True
# PID_FILE = '/tmp/magnum.pid'
# LOG_FILE = '/var/log/magnum.log'
