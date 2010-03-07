import os
from datetime import datetime
import email.utils as eut

from magnum import http

def StaticWrapper(fs_base,url_base):
    return lambda request: StaticHandler(request,fs_base,url_base)

class StaticHandler(http.Handler):

    def __init__(self,request,fs_base,url_base):
        self.request = request
        self.fs_base = fs_base
        self.url_base = url_base
    
    def response(self):

        if not self.request.path.startswith(self.url_base):
            return http.Http500Response()
        
        path = self.request.path.replace(self.url_base,"",1)

        full_path = os.path.normpath(self.fs_base + path)
        if not full_path.startswith(self.fs_base):
            return http.Http400Response()

        if not os.path.exists(full_path):
            return http.Http404Response(body="File Not Found")

        if_modified_since = self.request.headers.get("if-modified-since")
        if if_modified_since:
            try:
                if_modified_since = datetime.strptime(if_modified_since, '%a, %d %b %Y %H:%M:%S GMT')
            except ValueError:
                if_modified_since = None

        stats = os.stat(full_path)
        last_modified = datetime.fromtimestamp(stats[9])
        
        # Should add Content-Type detection based on file extension, but most browsers do this for us nowadays
        headers = {"Date" : datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT"),
                   "Server": "Magnum Web Server"}

        if self.request.headers.get("connection",'').lower() == "keep-alive":
            headers.update({"Keep-Alive" : "timeout=600, max=100",
                            "Connection" : "Keep-Alive",
                            "Last-Modified" : last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")})
    
        
        from magnum import config
        if getattr(config,'CACHE',False) and if_modified_since and last_modified<=if_modified_since:
            max_age = 60*60*24*365
            return http.Http304Response(max_age, self.request.version, headers)

        f = open(full_path, 'rb')
        body = f.read()
        f.close()

        return http.Response("200 OK", self.request.version, headers, body)


