import os, re
from datetime import datetime

from magnum import http

def DispatchWrapper(path_handlers):
    compiled_path_handlers = dict((re.compile(path),handler) for path,handler in path_handlers.iteritems() if path != "default")
    default_handler = path_handlers.get("default")
    return lambda request: DispatchHandler(request,compiled_path_handlers,default_handler)

class DispatchHandler(http.Handler):

    def __init__(self,request,compiled_path_handlers,default_handler):
        for compiled_path,handler in compiled_path_handlers.iteritems():
            if compiled_path.search(request.path):
                self.external_handler = handler(request)
                break
        else:
            self.external_handler = default_handler(request) 

    def response(self):

        if self.external_handler == None:
            return http.Http404Response()
        return self.external_handler.response()


