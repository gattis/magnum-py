#!/usr/bin/env python

import socket, select, thread, sys, signal, os, atexit, traceback, time
from cStringIO import StringIO
from multiprocessing import Queue,Value,Pool

from magnum import config,shared
from magnum.http import Parser,Http400Response,Http500Response

class RawHTTPData(object):

    def __init__(self, address):
        self.address = address
        self.head = StringIO()
        self.body = StringIO()
        self.active_buffer = self.head
        self.content_length = 0

    def write(self,bytes):
        if self.active_buffer == self.head:
            end = bytes.find('\r\n\r\n')
            if end < 0:
                self.head.write(bytes)
                return 

            self.head.write(bytes[:end])
            head_str = self.head.getvalue()
            self.active_buffer = self.body

            content_length_start = head_str.find("Content-Length:")
            if content_length_start < 0: return

            content_length_end = head_str.find("\r\n",content_length_start)
            try:
                self.content_length = int(head_str[content_length_start+15:content_length_end])
            except: return

            if self.content_length > 0:
                self.body.write(bytes[end+4:end+4+self.content_length])
        else:
            nbytes = self.content_length - self.body.tell()
            if nbytes > 0:
                self.body.write(bytes[:nbytes])
    
    def reset(self):
        self.head.reset()
        self.head.truncate()
        self.body.reset()
        self.body.truncate()
        self.active_buffer = self.head
        self.content_length = 0
        
    def complete(self):
        return self.active_buffer == self.body and self.body.tell() >= self.content_length
        

def serve_socket_requests(work_queue,completed_queue,shutdown_flag):

    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serversocket.bind(config.HOST)
    serversocket.listen(511)
    serversocket.setblocking(0)

    epoll = select.epoll()
    epoll.register(serversocket.fileno(), select.EPOLLIN | select.EPOLLET)

    connections = {}; requests = {}; responses = {};
    thread.start_new_thread(watch_completed_queue, (completed_queue,responses,epoll,shutdown_flag))

    while not shutdown_flag.value:
        try: events = epoll.poll(1)
        except IOError: break

        for fileno, event in events:
            if fileno == serversocket.fileno():
                try:
                    while True:
                        connection, address = serversocket.accept()
                        connection.setblocking(0)
                        cfileno = connection.fileno()
                        epoll.register(cfileno, select.EPOLLIN | select.EPOLLET)
                        connections[cfileno] = connection
                        requests[cfileno] = RawHTTPData(address)
                except socket.error, e:
                    pass

            elif event & select.EPOLLHUP:
                epoll.unregister(fileno)
                connections[fileno].close()
                del connections[fileno]

            elif event & select.EPOLLIN:
                connection = connections[fileno]
                request = requests[fileno]
                try:
                    while True:
                        incoming = connection.recv(1024)
                        if len(incoming) == 0:
                            try: connection.shutdown(socket.SHUT_RDWR)
                            except socket.error: pass
                            break
                        request.write(incoming)
                except socket.error, e:
                    code,message = e.args
                    if code != 11:
                        try: connection.shutdown(socket.SHUT_RDWR)
                        except socket.error: pass

                if request.complete():
                    work_queue.put((fileno,request.head.getvalue(),request.body.getvalue(),request.address))
                    request.reset()

            elif event & select.EPOLLOUT:
                
                response = responses.get(fileno)
                if response == None: continue
                rpos = response.tell()
                chunk = response.read()
                connection = connections[fileno]
                try:
                    while len(chunk) > 0:
                        byteswritten = connection.send(chunk)
                        response.seek(rpos+byteswritten)
                        rpos += byteswritten
                        chunk = response.read()
                except socket.error, e:
                    code,message = e.args
                    if code != 11:
                        try: connection.shutdown(socket.SHUT_RDWR)
                        except socket.error: pass
                    response.seek(rpos)
                if len(chunk) == 0:
                    del responses[fileno]
                    if "keep-alive" in response.getvalue():
                        epoll.modify(fileno,  select.EPOLLIN | select.EPOLLET)
                    else:
                        epoll.modify(fileno, select.EPOLLET)
                        try: connections[fileno].shutdown(socket.SHUT_RDWR)
                        except socket.error: pass
                        del requests[fileno]

    epoll.unregister(serversocket.fileno())
    epoll.close()
    serversocket.close()


def watch_completed_queue(completed_queue,responses,epoll,shutdown_flag):
    while not shutdown_flag.value:
        fileno, response_string = completed_queue.get(block = True)
        responses[fileno] = StringIO(response_string)
        try:
            epoll.modify(fileno, select.EPOLLOUT | select.EPOLLET)
        except IOError:
            pass
            
            

def worker(work_queue,completed_queue,shutdown_flag):

    while not shutdown_flag.value:
        fileno, head, body, address = work_queue.get(block = True)
        if fileno == -1: return
            
        parser = Parser(head,body)
        request = parser.parse()
        if request == None:
            response = Http400Response().output()
        else:
            addr,port = address
            request.remote_addr = addr
            request.remote_port = port
            log("%s - %s" %( request.remote_addr, request.path ))
            handler = config.HANDLER_CLASS(request)
            try:
                response = handler.response().output()
            except:
                exc = traceback.format_exc()
                log(exc)
                if config.DEBUG:
                    response = exc
                else:
                    response = Http500Response().output()
            
        completed_queue.put((fileno,response))




def log(message):
    print "%s - %s" % (time.time(), message)

def daemonize():

    pid = os.fork()
    if pid > 0: sys.exit(0)
    os.setsid()
    pid = os.fork()
    if pid > 0: sys.exit(0)

    os.chdir("/")
    os.umask(0)

    in_redir = open('/dev/null','r')
    os.dup2(in_redir.fileno(),sys.stdin.fileno())

    out_redir = open(config.LOG_FILE,'a')
    os.dup2(out_redir.fileno(),sys.stdout.fileno())

    err_redir = open(config.LOG_FILE,'a',0)
    os.dup2(err_redir.fileno(),sys.stderr.fileno())

    atexit.register(lambda: os.remove(config.PID_FILE))
    open(config.PID_FILE,'w').write("%d" % os.getpid())


def cleanup(workerpool,work_queue,shutdown_flag):
    log("shutting down")
    shutdown_flag.value = 1
    for i in xrange(config.WORKERS): work_queue.put((-1,None,None,None))
    workerpool.close()
    workerpool.join()
    

def start(): 
    
    try:
        fpid = open(config.PID_FILE,'r')
        print "Already running with proccess id %s!" % fpid.read()
        return
    except:
        print "Starting..."

    daemonize()
    log("server started")

    shutdown_flag = Value('b',0)
    work_queue = Queue()
    completed_queue = Queue()
    shared.instantiate()

    workerpool = Pool(processes = config.WORKERS, initializer = worker, initargs = (work_queue,completed_queue,shutdown_flag))

    signal.signal(signal.SIGTERM, lambda signum, stack_frame: cleanup(workerpool,work_queue,shutdown_flag))
    try:
        serve_socket_requests(work_queue,completed_queue,shutdown_flag)
    except:
        print "Fatal Exception:"
        traceback.print_exc()
        cleanup(workerpool,work_queue,shutdown_flag)

def stop():
    
    try:
        fpid = open(config.PID_FILE,'r')
        fpid = int(fpid.read())
        
        try: os.kill(fpid, signal.SIGTERM)
        except: pass
        print "Stopped."
    except:
        print "Not running!"
    
    
def restart():
    stop()
    time.sleep(1)
    start()

if __name__ == '__main__':

    if len(sys.argv) == 2:
        try:
            {'start': start,
             'stop': stop,
             'restart': restart}[sys.argv[1]]()
        except KeyError:
            print "Invalid Command!\n\nusage: serve.py start|stop|restart"

    else:
        print "usage: serve.py start|stop|restart"
        sys.exit(2)
