#!/usr/bin/env python

import socket, select, sys, signal, os, atexit, traceback, thread, time
from cStringIO import StringIO

from magnum import config,shared,ipc
from magnum.http import RawHTTPData, Parser, Http400Response, Http500Response


def serve_socket_requests(work_queue,shutdown_flag):

    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serversocket.bind(config.HOST)
    serversocket.listen(511)
    serversocket.setblocking(0)

    trigger = ipc.EdgeTrigger(serversocket.fileno(), work_queue.response_rfd)

    connections = {}; requests = {}; responses = {};

    while not shutdown_flag.is_set():
        events = trigger.events(1)
        for fileno, event in events:

            if trigger.is_hup(event):
                if trigger.handle_hup(fileno,event,connections):
                    continue

            if fileno == serversocket.fileno():
                try:
                    while True:
                        connection, address = serversocket.accept()
                        connection.setblocking(0)
                        cfileno = connection.fileno()
                        trigger.register(cfileno)
                        connections[cfileno] = connection
                        requests[cfileno] = RawHTTPData(address)
                except socket.error, e:
                    code,message = e.args
                    if trigger.is_fatal(code):
                        try: connection.shutdown(socket.SHUT_RDWR)
                        except socket.error: pass

            elif fileno == work_queue.response_rfd:
                completed = work_queue.get_response()
                if completed != None:
                    cfileno, response, keep_alive = completed
                    try: 
                        trigger.modify_to_write(cfileno)
                        responses[cfileno] = (StringIO(response), keep_alive)
                    except: pass

            elif trigger.is_read(event):
                connection = connections[fileno]
                request = requests[fileno]
                try:
                    while True:
                        incoming = connection.recv(1024)
                        if len(incoming) == 0:
                            connection.shutdown(socket.SHUT_RDWR)
                            break
                        request.write(incoming)
                except socket.error, e:
                    code,message = e.args
                    if trigger.is_fatal(code): 
                        try: connection.shutdown(socket.SHUT_RDWR)
                        except socket.error: pass

                if request.complete():
                    work_queue.submit_request(fileno,request.address,request.head.getvalue(),request.body.getvalue())
                    request.reset()
                    trigger.stop_reads(fileno)
                    
            elif trigger.is_write(event):
                
                response,keep_alive = responses[fileno]
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
                    if trigger.is_fatal(code):
                        try: connection.shutdown(socket.SHUT_RDWR)
                        except socket.error: pass
                    response.seek(rpos)
                if len(chunk) == 0:
                    del responses[fileno]
                    trigger.stop_writes(fileno)
                    if keep_alive:
                        trigger.modify_to_read(fileno)
                    else:
                        try: connections[fileno].shutdown(socket.SHUT_RDWR)
                        except socket.error: pass
                        trigger.terminate(fileno,connections)

    trigger.close(serversocket.fileno())
    serversocket.close()


def worker_process(work_queue,shutdown_flag):
    for i in xrange(config.WORKER_THREADS_PER_PROCESS):
        thread.start_new_thread(worker_thread, (work_queue, shutdown_flag))
    try:
        while True: time.sleep(1)
    except: return


def worker_thread(work_queue,shutdown_flag):

    while not shutdown_flag.is_set():
        fileno, address, head, body = work_queue.get_request()
        if fileno == 0: 
            thread.interrupt_main()
            return
            
        parser = Parser(head,body)
        request = parser.parse()
        if request == None:
            response = Http400Response()
        else:
            request.remote_addr, request.remote_port = address
            request._work_queue = work_queue
            log("%s - %s" %( request.remote_addr, request.path ))
            handler = config.HANDLER_CLASS(request)
            try:
                response = handler.response()
            except:
                exc = traceback.format_exc()
                log(exc)
                if config.DEBUG:
                    response = Http500Response(exc)
                else:
                    response = Http500Response()
        work_queue.submit_response(fileno,response)


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

    open(config.PID_FILE,'w').write("%d" % os.getpid())


def cleanup(workerpool,work_queue,shutdown_flag):
    log("shutting down")
    shutdown_flag.set()
    for i in xrange(config.WORKER_PROCESSES * config.WORKER_THREADS_PER_PROCESS): 
        work_queue.submit_request(0,0,'','')
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

    shutdown_flag = ipc.Flag()
    work_queue = ipc.WorkQueue()
    shared.instantiate()

    workerpool = ipc.ProcessPool(config.WORKER_PROCESSES, worker_process, (work_queue,shutdown_flag))

    atexit.register(lambda: os.remove(config.PID_FILE))
    signal.signal(signal.SIGTERM, lambda signum, stack_frame: cleanup(workerpool,work_queue,shutdown_flag))

    try:
        serve_socket_requests(work_queue,shutdown_flag)
    except:
        print "Fatal Exception:"
        traceback.print_exc()
        cleanup(workerpool,work_queue,shutdown_flag)

def stop():
    
    try:
        fpid = open(config.PID_FILE,'r')
        fpid = int(fpid.read())
        
        while True:
            try: os.kill(fpid, signal.SIGTERM)
            except OSError: break
            time.sleep(0.2)
            
        print "Stopped."
    except IOError:
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
