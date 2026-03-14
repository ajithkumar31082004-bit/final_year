import time
import threading
from collections import defaultdict, deque


_LOCK = threading.Lock()
_BUCKETS = defaultdict(deque)


def check_rate_limit(key: str, limit: int, window_seconds: int):
    """
    Simple in-memory rate limiter.
    Returns (allowed: bool, retry_after_seconds: int|None).
    """
    now = time.time()
    with _LOCK:
        q = _BUCKETS[key]
        cutoff = now - window_seconds
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= limit:
            retry_after = int(window_seconds - (now - q[0])) if q else window_seconds
            return False, max(retry_after, 1)
        q.append(now)
        return True, None
