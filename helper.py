""" Helper functions """

def memoize(function):
    """ Memoizing decorator serving as a cache for functions
    whose state is memoized in dictionaries """

    _memoized = {}

    def wrapper(instance, *args):
        # Create a place holder for the instance
        try:
            _memoized[instance]
        except KeyError:
            _memoized[instance] = {}

        # Cache the functions output or return from
        # previously cached data.
        try:
            return _memoized[instance][args]
        except KeyError:
            _memoized[instance][args] = function(instance, *args)
            return _memoized[instance][args]

    return wrapper

def int2bin(n, count=32):
    """ Returns the binary of integer n as string, using count number of digits """

    return "".join([str((n >> y) & 1) for y in range(count-1, -1, -1)])

