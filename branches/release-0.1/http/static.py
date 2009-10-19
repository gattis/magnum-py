import os
from datetime import datetime

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

        f = open(full_path, 'rb')
        body = f.read()
        f.close()

        # Should add Content-Type detection based on file extension, but most browsers do this for us nowadays
        headers = {"Date" : datetime.now().strftime("%a, %d %b %Y %H:%M:%S EDT"),
                   "Server": "Magnum Web Server"}

        if self.request.headers.get("connection",'').lower() == "keep-alive":
            headers.update({"Keep-Alive" : "timeout=600, max=100",
                            "Connection" : "Keep-Alive"})
    
        return http.Response("200 OK", self.request.version, headers, body)


