import os, re
from datetime import datetime

from magnum import http

def PathDispatchWrapper(path_handlers):
    compiled_path_handlers = dict((re.compile(path),handler) for path,handler in path_handlers.iteritems() if path != "default")
    default_handler = path_handlers.get("default")
    return lambda request: PathDispatchHandler(request,compiled_path_handlers,default_handler)

class PathDispatchHandler(http.Handler):

    def __init__(self,request,compiled_path_handlers,default_handler):
        for compiled_path,handler in compiled_path_handlers.iteritems():
            if compiled_path.search(request.path):
                self.external_handler = handler(request)
                break
        else:
            self.external_handler = default_handler(request) 

    def response(self):

        if self.external_handler is None:
            return http.Http404Response()
        return self.external_handler.response()


def HostDispatchWrapper(host_handlers):
    default_handler = host_handlers.get("default")
    host_handlers = dict((host,handler) for host,handler in host_handlers.iteritems() if host != "default")
    return lambda request: HostDispatchHandler(request,host_handlers,default_handler)

class HostDispatchHandler(http.Handler):
    
    def __init__(self,request,host_handlers,default_handler):

        host = request.headers.get("host")
        if host is None:
            self.external_handler = default_handler(request)
            return

        request_host = host.split(":")[0]

        for host,handler in host_handlers.iteritems():
            if host == request_host:
                self.external_handler = handler(request)
                break
        else:
            self.external_handler = default_handler(request)

    def response(self):
        
        if self.external_handler is None:
            return http.Http404Response()
        return self.external_handler.response()


def PortDispatchWrapper(port_handlers):
    default_handler = port_handlers.get("default")
    port_handlers = dict((port,handler) for port,handler in port_handlers.iteritems() if port != "default")
    return lambda request: PortDispatchHandler(request,port_handlers,default_handler)

class PortDispatchHandler(http.Handler):
    
    def __init__(self,request,port_handlers,default_handler):

        host = request.headers.get("host")
        if host is None:
            self.external_handler = default_handler(request)
            return

        host = host.split(":")
        request_port = 80
        if len(host) == 2:
            request_port = int(host[1])
        
        for port,handler in port_handlers.iteritems():
            if port == request_port:
                self.external_handler = handler(request)
                break
        else:
            self.external_handler = default_handler(request)

    def response(self):
        
        if self.external_handler is None:
            return http.Http404Response()
        return self.external_handler.response()
    

def RedirectWrapper(location):
    return lambda request: RedirectHandler(request,location)

class RedirectHandler(http.Handler):

    def __init__(self,request,location):
        self.location = location

    def response(self):
        return http.Http301Response(self.location)
