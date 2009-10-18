#!/usr/bin/env python

import socket, select, thread, sys, signal, os, atexit, traceback, time
from cStringIO import StringIO as StringBuffer
from multiprocessing import Queue,Value,Pool

from magnum import config,shared
from magnum.http import Parser,Http400Response,Http500Response

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
						requests[cfileno] = StringBuffer()
				except socket.error:
					pass
			elif event & select.EPOLLIN:
				try:
					# TODO: bail out of this while loop if we sense an attack
					while True:
						incoming = connections[fileno].recv(1024)
						if incoming == '': break
						requests[fileno].write(incoming)
				except socket.error:
					pass
				request_string = requests[fileno].getvalue()
				if '\n\n' in request_string or '\n\r\n' in request_string:
					#epoll.modify(fileno, select.EPOLLOUT | select.EPOLLET)
					work_queue.put((fileno,request_string))
			elif event & select.EPOLLOUT:
				
				response_string = responses.get(fileno)
				if response_string == None:
					continue
				try:
					while len(responses[fileno]) > 0:
						byteswritten = connections[fileno].send(responses[fileno])
						responses[fileno] = responses[fileno][byteswritten:]
				except socket.error:
					pass
				if len(responses[fileno]) == 0:
					del responses[fileno]
					if "keep-alive" in response_string.lower():
						epoll.modify(fileno,  select.EPOLLIN | select.EPOLLET)
						requests[fileno] = StringBuffer()
					else:
						epoll.modify(fileno, select.EPOLLET)
						connections[fileno].shutdown(socket.SHUT_RDWR)
						del requests[fileno]
			elif event & select.EPOLLHUP:
				epoll.unregister(fileno)
				connections[fileno].close()
				del connections[fileno]

	epoll.unregister(serversocket.fileno())
	epoll.close()
	serversocket.close()


def watch_completed_queue(completed_queue,responses,epoll,shutdown_flag):
	while not shutdown_flag.value:
		fileno, response_string = completed_queue.get(block = True)
		responses[fileno] = response_string
		try:
			epoll.modify(fileno, select.EPOLLOUT | select.EPOLLET)
		except IOError:
			pass
			
			

def worker(work_queue,completed_queue,shutdown_flag):

	while not shutdown_flag.value:
		fileno, request_string = work_queue.get(block = True)
		if fileno == -1 and request_string == "DIE": return
			
		parser = Parser(request_string)
		request = parser.parse()
		if request == None:
			response = Http400Response().output()
		else:
			log(request.path)
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
	for i in xrange(config.WORKERS): work_queue.put((-1,"DIE"))
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





	
