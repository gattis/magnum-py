from datetime import datetime
from cStringIO import StringIO


class Parser(object):

    def __init__(self,head,body):
        self.head = head
        self.body = body

    def parse(self):
        
        heading = self.head.split("\r\n")
        command = heading[0].split()
        version = (0,9)
        if len(command) == 3:
            method, path, version = command
            if not version.startswith('HTTP/'): return None
            version = version.split('/',1)[1]
            version_parts = version.split(".")
            if len(version_parts) != 2: return None
            try:
                version = (int(version_parts[0]), int(version_parts[1]))
            except: return None
            if version >= (2,0): return None 
        elif len(command) == 2:
            method, path = command
            if method != "GET": return None
        else: return None
    
        headers = {}
        for header in heading[1:]:
            parts = header.split(":",1)
            if len(parts) == 2:
                key,val = parts
                headers[key.strip().lower()] = val.strip()
            elif len(parts) == 1:
                headers[parts[0]] = ''
            else: return None

        return Request(method, path, version, headers, self.body)


class Request(object):

    def __init__(self, method = "GET", path = "/", version = (1,0), headers = None, body = "", remote_addr = None, remote_port = None):
        self.method = method
        self.path = path
        self.version = version
        self.headers = headers if type(headers) == dict else {}
        self.body = body
        self.remote_addr = remote_addr
        self.remote_port = remote_port




# Base Handler Class - Override me
class Handler(object):

    def __init__(self,request):
        self.request = request

    
    def response(self):
    
        headers = {"Date" : datetime.now().strftime("%a, %d %b %Y %H:%M:%S EDT"),
                   "Server": "Magnum Web Server",
                   "Content-Type": "text/html; charset=UTF-8"}

        if self.request.headers.get("connection",'').lower() == "keep-alive":
            headers.update({"Keep-Alive" : "timeout=600, max=100",
                            "Connection" : "Keep-Alive"})
    
        return Response("200 OK", self.request.version, headers, "This website is proudly served by the Magnum Web Server\n")
        


class Response(object):

    def __init__(self, code = "200 OK", version = (1,0), headers = None, body = ''):
        self.code = code
        self.version = version
        self.headers = headers if type(headers) == dict else {}
        self.body = body
        self.headers["Content-Length"] = len(self.body)
        
    def output(self):
        out = StringIO()
        out.write("HTTP/")
        out.write('.'.join(map(str,self.version)))
        out.write(" %s\r\n" % self.code)
        for header,val in self.headers.iteritems():
            out.write("%s: %s\r\n" % (header,val))
        out.write("\r\n")
        out.write(self.body)
        return out.getvalue()



class Http400Response(Response):
    def __init__(self,body = '', version = (1,1), headers = None):
        Response.__init__(self, code = "400 Bad Request", version = version, headers = headers, body = body)

class Http404Response(Response):
    def __init__(self,body = '', version = (1,1), headers = None):
        Response.__init__(self, code = "404 Not Found", version = version, headers = headers, body = body)

class Http500Response(Response):
    def __init__(self,body = '', version = (1,1), headers = None):
        Response.__init__(self, code = "500 Internal Server Error", version = version, headers = headers, body = body)
