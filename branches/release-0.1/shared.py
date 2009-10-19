


objects = {}

def instantiate():

    # This function is called once during server startup. Modify the global 'objects' dict with of instantiated
    # shared objects that you wish to store in the parent process and have access to from child request handler 
    # processes. Each object must support being shared via the multiproccessing module or else  the object will 
    # just be copied into the children. See http://docs.python.org/library/multiprocessing.html
    #
    # For example, in this function you might put:
    #
    #   import multiprocessing
    #   objects['num_requests'] = multiprocessing.Value('i',0)
    #
    # And in your request handler, put:
    #
    #   from magnum.shared import objects
    #   objects['num_requests'].value += 1

    return




