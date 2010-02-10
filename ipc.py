import fcntl,mmap,os,select,struct,sys,traceback
from cStringIO import StringIO

try:
    from multiprocessing import Semaphore
except ImportError:
    import ctypes
    class Semaphore(object):

        def __init__(self,value = 1):
            librt = ctypes.cdll.LoadLibrary("librt.so.1")
            buffer = mmap.mmap(-1,1)
            self.sem = ctypes.byref(ctypes.c_ubyte.from_buffer(buffer))
            self._sem_wait = librt.sem_wait
            self._sem_post = librt.sem_post
            librt.sem_init(sem,1,value)

        def acquire(self):
            self._sem_wait(self.sem)
            
        def release(self):
            self._sem_post(self.sem)

class Flag(object):

    def __init__(self):
        self.shm = mmap.mmap(-1,1)
        self.shm[0] = '\x00'

    def is_set(self):
        return self.shm[0] == '\x01'

    def set(self):
        self.shm[0] = '\x01'


REQUEST_HEADER = struct.Struct("LBBBBHLL")
RESPONSE_HEADER = struct.Struct("LL")

class WorkQueue(object):

    def __init__(self):
        self.request_rfd, self.request_wfd = os.pipe()
        self.response_rfd, self.response_wfd = os.pipe()
        self.response_reader = ResponseReader(self.response_rfd)
        self.request_sem = Semaphore()
        self.response_sem = Semaphore()
        
    def submit_request(self, id, address, head, body):
        try:
            ip_str,port = address
            ipa, ipb, ipc, ipd = map(int,ip_str.split("."))
        except: 
            port = ipa = ipb = ipc = ipd = 0
        os.write(self.request_wfd, REQUEST_HEADER.pack(id,ipa,ipb,ipc,ipd,port,len(head),len(body)) + head + body)
        
    def get_request(self):
        self.request_sem.acquire()
        header = ''
        bytes_to_read = REQUEST_HEADER.size
        while bytes_to_read:
            header += os.read(self.request_rfd, bytes_to_read) 
            bytes_to_read = REQUEST_HEADER.size - len(header)
        id,ipa,ipb,ipc,ipd,port,head_len,body_len = REQUEST_HEADER.unpack(header)

        head = StringIO()
        bytes_to_read = head_len
        while bytes_to_read:
            head.write(os.read(self.request_rfd, bytes_to_read))
            bytes_to_read = head_len - head.tell()

        body = StringIO()
        bytes_to_read = body_len
        while bytes_to_read:
            body.write(os.read(self.request_rfd, bytes_to_read))
            bytes_to_read = body_len - body.tell()

        self.request_sem.release()
        return id, ('.'.join(map(str,[ipa,ipb,ipc,ipd])), port), head.getvalue(), body.getvalue()

    def submit_response(self, id, response):
        self.response_sem.acquire()
        response_output = response.output()
        keep_alive = '\x01' if response.headers.get("Connection") == "Keep-Alive" else '\x00'
        os.write(self.response_wfd, RESPONSE_HEADER.pack(id,len(response_output)) + response_output + keep_alive)
        self.response_sem.release()

    def get_response(self):
        return self.response_reader.read()



class ResponseReader(object):

    def __init__(self,fd):
        fcntl.fcntl(fd,fcntl.F_SETFL,os.O_NONBLOCK)
        self.fd = fd
        self.data = StringIO()
        self.id = self.len = None

    def read(self):
        if self.id == None:
            bytes_to_read = RESPONSE_HEADER.size - self.data.tell()
            while bytes_to_read:
                try:
                    self.data.write(os.read(self.fd,bytes_to_read))
                    bytes_to_read = RESPONSE_HEADER.size - self.data.tell()
                except OSError: break
            if bytes_to_read == 0:
                self.id,self.len = RESPONSE_HEADER.unpack(self.data.getvalue())
                self.data = StringIO()

        if self.len != None:
            bytes_to_read = self.len - self.data.tell()
            while bytes_to_read:
                try:
                    self.data.write(os.read(self.fd,bytes_to_read))
                    bytes_to_read = self.len - self.data.tell()
                except OSError: break
            if bytes_to_read == 0:
                try:
                    keep_alive = os.read(self.fd,1)
                except OSError: return None
                response = self.data.getvalue()
                id = self.id
                self.data = StringIO()
                self.id = self.len = None
                return id,response,keep_alive == '\x01'
        return None

class EdgeTrigger(object):
    
    def __init__(self, socket_fd, queue_fd):
        if hasattr(select,'epoll'): self.is_epoll = True
        elif hasattr(select,'kqueue'): self.is_epoll = False
        else: raise Exception("Your operating system must support epoll or kqueue")
        if self.is_epoll:
            self.trigger = select.epoll()
            self.trigger.register(socket_fd, select.EPOLLIN | select.EPOLLET)
            self.trigger.register(queue_fd, select.EPOLLIN | select.EPOLLET)
        else:
            self.trigger = select.kqueue()
            self.trigger.control([select.kevent(socket_fd, select.KQ_FILTER_READ, select.KQ_EV_ADD)],0)
            self.trigger.control([select.kevent(queue_fd, select.KQ_FILTER_READ, select.KQ_EV_ADD)],0)
            
            
    def events(self, nevents):
        if self.is_epoll:
            try: return self.trigger.poll(nevents)
            except IOError: return []
        else:
            return [(e.ident,(e.filter,e.flags)) for e in self.trigger.control(None,1)]

    def modify_to_write(self, fileno):
        if self.is_epoll: self.trigger.modify(fileno, select.EPOLLOUT | select.EPOLLET)
        else: self.trigger.control([select.kevent(fileno, select.KQ_FILTER_WRITE, select.KQ_EV_ADD)],0)

    def modify_to_read(self, fileno):
        if self.is_epoll: self.trigger.modify(fileno,  select.EPOLLIN | select.EPOLLET)
        else: self.trigger.control([select.kevent(fileno, select.KQ_FILTER_READ, select.KQ_EV_ADD)],0)

    def stop_reads(self, fileno):
        if self.is_epoll: self.trigger.modify(fileno, select.EPOLLET)
        else: self.trigger.control([select.kevent(fileno, select.KQ_FILTER_READ, select.KQ_EV_DELETE)],0)

    def stop_writes(self, fileno):
        if self.is_epoll: self.trigger.modify(fileno, select.EPOLLET)
        else: self.trigger.control([select.kevent(fileno, select.KQ_FILTER_WRITE, select.KQ_EV_DELETE)],0)

    def register(self, fileno):
        if self.is_epoll: self.trigger.register(fileno, select.EPOLLIN | select.EPOLLET)
        else: self.trigger.control([select.kevent(fileno, select.KQ_FILTER_READ, select.KQ_EV_ADD)],0)

    def handle_hup(self, fileno, event, connections):
        if self.is_epoll:
            self.trigger.unregister(fileno)
            try:
                connections[fileno].close()
                del connections[fileno]
            except: pass
        else:
            filter,flags = event
            if filter == select.KQ_FILTER_READ:
                self.trigger.control([select.kevent(fileno, select.KQ_FILTER_READ, select.KQ_EV_DELETE)],0)
            elif filter == select.KQ_FILTER_WRITE:
                self.trigger.control([select.kevent(fileno, select.KQ_FILTER_WRITE, select.KQ_EV_DELETE)],0)
            
    def terminate(self, fileno, connections):
        if self.is_epoll: return
        try:
            connections[fileno].close()
            del connections[fileno]
        except: pass

    def is_read(self, event):
        if self.is_epoll: return event & select.EPOLLIN
        else:
            filter,flags = event
            return filter == select.KQ_FILTER_READ

    def is_write(self, event):
        if self.is_epoll: return event & select.EPOLLOUT
        else:
            filter,flags = event
            return filter == select.KQ_FILTER_WRITE

    def is_hup(self, event):
        if self.is_epoll: return event & select.EPOLLHUP
        else:
            filter,flags = event
            return flags & select.KQ_EV_EOF

    def is_fatal(self, error_code):
        if self.is_epoll:
            return error_code != 11
        else:
            return error_code != 35

    def close(self, socket_fd):
        if self.is_epoll: self.trigger.unregister(socket_fd)
        else: self.trigger.control([select.kevent(socket_fd, select.KQ_FILTER_READ, select.KQ_EV_DELETE)],0)
        self.trigger.close()
                

class ProcessPool(object):
    
    def __init__(self, nprocs, fn, args):

        self.pids = []
        for i in xrange(nprocs):
            pid = os.fork()
            if pid > 0:
                self.pids.append(pid)
            else: 
                try:
                    apply(fn,args)
                except:
                    print "Worker %s threw an Exception:" % i
                    traceback.print_exc()
                finally:
                    sys.exit(0)

    def join(self):
        for pid in self.pids:
            try:
                os.waitpid(pid,0)
            except OSError: continue
