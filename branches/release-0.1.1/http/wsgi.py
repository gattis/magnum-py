from io import StringIO
import sys

from magnum import http

def WSGIWrapper(app):
    return lambda request: WSGIHandler(request,app)

class WSGIHandler(http.Handler):



    def __init__(self,request,app):
        self.request = request
        self.app = app
    
    def response(self):
    
        from magnum import config
        
        path_split = self.request.path.split("?",1)
        path_info,query_string = {1: (path_split[0], ""), 2: path_split}[len(path_split)]

        environ = {"REQUEST_METHOD": self.request.method,
                   "SCRIPT_NAME": "",
                   "PATH_INFO": path_info,
                   "QUERY_STRING": query_string,
                   "CONTENT_TYPE": self.request.headers.get('content-type',''),
                   "CONTENT_LENGTH": self.request.headers.get('content-length',''),
                   "SERVER_NAME": config.HOST[0],
                   "SERVER_PORT": config.HOST[1],
                   "REMOTE_ADDR": self.request.remote_addr,
                   "wsgi.version": (1,0),
                   "wsgi.url_scheme": "http",
                   "wsgi.input": StringIO(self.request.body),
                   "wsgi.errors": sys.stderr,
                   "wsgi.multithread": False,
                   "wsgi.multiprocess": True,
                   "wsgi.run_once": False}

        for key,val in self.request.headers.iteritems():
            key = key.replace('-','_').upper()
            if key in environ: continue
            if 'HTTP_'+key in environ:
                environ['HTTP_'+key] += ','+val
            else:
                environ['HTTP_'+key] = val

        body = []
        status_headers = [None,None]
        def start_response(status,headers):
            status_headers[:] = [status,headers]
            return body.append
        app_iter = self.app(environ, start_response)
        try:
            for item in app_iter:
                body.append(item)
        finally:
            if hasattr(app_iter,'close'):
                app_iter.close()
        
        status,headers,body = status_headers[0], dict(status_headers[1]), ''.join(body)

        if self.request.headers.get("connection",'').lower() == "keep-alive":
            headers.update({"Keep-Alive" : "timeout=600, max=100",
                            "Connection" : "Keep-Alive"})
    
        return http.Response(status, self.request.version, headers, body)


