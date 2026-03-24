"""Rate limiting and request throttling."""

import time
from collections import defaultdict
from typing import Optional


class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""

    def __init__(self, requests_per_second: float = 10, burst_size: Optional[int] = None):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Allowed requests per second
            burst_size: Maximum burst size (defaults to requests_per_second)
        """
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size or int(requests_per_second * 2)
        self.buckets = defaultdict(lambda: {"tokens": self.burst_size, "last_update": time.time()})

    def is_allowed(self, client_id: str) -> bool:
        """
        Check if client is allowed to make a request.

        Args:
            client_id: Unique client identifier (IP address, etc.)

        Returns:
            True if allowed, False if rate limited
        """
        current_time = time.time()
        bucket = self.buckets[client_id]

        # Calculate tokens to add based on time elapsed
        time_elapsed = current_time - bucket["last_update"]
        tokens_to_add = time_elapsed * self.requests_per_second
        bucket["tokens"] = min(self.burst_size, bucket["tokens"] + tokens_to_add)
        bucket["last_update"] = current_time

        # Check if we have a token
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True

        return False

    def get_retry_after(self, client_id: str) -> float:
        """
        Get seconds to wait before retry.

        Args:
            client_id: Unique client identifier

        Returns:
            Seconds to wait
        """
        bucket = self.buckets[client_id]
        if bucket["tokens"] < 1:
            return (1 - bucket["tokens"]) / self.requests_per_second
        return 0


class EndpointRateLimiter:
    """Rate limiter for specific endpoints."""

    def __init__(self):
        """Initialize endpoint rate limiter."""
        self.limiters = {
            "/api/upload": RateLimiter(requests_per_second=5),  # 5 uploads/sec
            "/api/list": RateLimiter(requests_per_second=20),  # 20 listings/sec
            "/download/": RateLimiter(requests_per_second=10),  # 10 downloads/sec
            "default": RateLimiter(requests_per_second=50),  # 50 req/sec default
        }

    def is_allowed(self, endpoint: str, client_id: str) -> bool:
        """
        Check if request is allowed for endpoint.

        Args:
            endpoint: API endpoint path
            client_id: Client identifier (IP)

        Returns:
            True if allowed, False if rate limited
        """
        limiter = self.limiters.get(endpoint)
        if not limiter:
            # Find matching limiter
            for key, lim in self.limiters.items():
                if key != "default" and endpoint.startswith(key):
                    limiter = lim
                    break
            if not limiter:
                limiter = self.limiters["default"]

        return limiter.is_allowed(client_id)

    def get_retry_after(self, endpoint: str, client_id: str) -> float:
        """Get retry-after time for endpoint."""
        limiter = self.limiters.get(endpoint)
        if not limiter:
            for key, lim in self.limiters.items():
                if key != "default" and endpoint.startswith(key):
                    limiter = lim
                    break
            if not limiter:
                limiter = self.limiters["default"]

        return limiter.get_retry_after(client_id)
