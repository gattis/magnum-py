Magnum is a pure python HTTP server that is fast and efficient with resources.  It is ideal for serving dynamic python-generated pages.

## Features: ##
  * Written in pure python
    * Elegant, extensible and customizable
    * No connectors needed to serve python web applications such as Django
  * Event-driven non-blocking socket I/O (epoll for Linux, kqueue for BSD)
    * Can handle many simultaneous keep-alive connections to minimize latency
    * Works well with slow clients
    * Much faster than apache prefork and worker models
  * Multi-process queue-based worker pool
    * Shuns the one-thread-per-request paradigm to ensure system resources are available
    * Uses python 2.6's multiprocessing features to divide up labor and manage resources efficiently
    * Minimal collateral damage when under heavy load
  * Shared memory pool
    * Great for maintaining large per-machine in-memory caches to improve performance
  * Supports WSGI and static file serving out of the box
  * Simple config.py file supporting per-path/host/port virtual hosts

## Requirements: ##
  * Linux/BSD variant (OSX works)
  * Python 2.6+ (3.0 is untested)

## 1.0 Roadmap: ##
  * Zero-downtime updates (no restart needed for changes to the app code layer)
  * Reliability and security improvements
    * Standard security audits
    * Automatic chroot'ing
    * Security ideas from [OKWS](http://pdos.csail.mit.edu/~max/docs/okws.pdf)
    * Test suites and benchmarks
  * Faster serving of static files (using sendfile system call where available)
  * HTTPS support
  * Basic and Digest authentication out of the box
  * Support gzip / deflate
  * Built-in rate limiting module
  * HTML GUI admin interface

## Acknowledgements: ##
  * [epoll socket programming examples](http://scotdoyle.com/python-epoll-howto.html)
  * [python daemon example code](http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/)