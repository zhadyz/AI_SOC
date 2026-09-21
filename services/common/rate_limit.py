"""Bounded, thread-safe sliding-window limits for a single service process."""
from collections import OrderedDict, deque
import math
import threading
import time


class SlidingWindowRateLimiter:
    def __init__(self, requests_per_window=600, window_seconds=60, max_clients=10000, clock=time.monotonic):
        if min(requests_per_window, window_seconds, max_clients) <= 0:
            raise ValueError("Rate-limit values must be positive")
        self.limit, self.window, self.capacity = requests_per_window, window_seconds, max_clients
        self.clock = clock
        self.clients = OrderedDict()
        self.lock = threading.Lock()

    def is_allowed(self, client_id):
        with self.lock:
            now = self.clock()
            # Evict only expired buckets; rotating identities cannot reset an
            # existing client's exhausted allowance by evicting its bucket.
            while self.clients:
                _, oldest = next(iter(self.clients.items()))
                if oldest[-1] > now - self.window:
                    break
                self.clients.popitem(last=False)
            if client_id not in self.clients and len(self.clients) >= self.capacity:
                return False, math.ceil(self.window)
            timestamps = self.clients.setdefault(client_id, deque())
            while timestamps and timestamps[0] <= now - self.window:
                timestamps.popleft()
            if len(timestamps) >= self.limit:
                return False, max(1, math.ceil(timestamps[0] + self.window - now))
            timestamps.append(now)
            self.clients.move_to_end(client_id)
            return True, None
