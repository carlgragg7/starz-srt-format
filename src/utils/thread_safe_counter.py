from threading import Lock

# thread safe counter class
class ThreadSafeCounter():
    def __init__(self):
        self._counter = 0
        self._lock = Lock()

    # increment the counter
    def increment(self):
        with self._lock:
            self._counter += 1
            return self._counter

    # get the counter value
    def value(self):
        with self._lock:
            return self._counter

    def set_value(self, value):
        with self._lock:
            self._counter = value
            return self._counter
