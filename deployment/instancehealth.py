import threading


class InstanceHealth(object):
    """Thread safe object to communicate between the worker thread and the API thread."""

    def __init__(self):
        self._errors = {}
        self._lock = threading.Lock()

    def add_degraded(self, key, error):
        with self._lock:
            if key not in self._errors:
                self._errors[key] = []
            self._errors[key].append(error)

    def set_ok(self, key):
        with self._lock:
            if key in self._errors:
                del self._errors[key]

    def get_status(self):
        with self._lock:
            return {'degraded': len(self._errors), 'errors': self._errors}
