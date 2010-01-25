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

    def epoll_register(self, epoll):
        epoll.register(self.response_rfd, select.EPOLLIN | select.EPOLLET)


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
