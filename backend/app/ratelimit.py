import time


class RateLimiter:
    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self.hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        lst = [t for t in self.hits.get(key, []) if now - t < self.window]
        lst.append(now)
        self.hits[key] = lst
        return len(lst) <= self.limit


order_limiter = RateLimiter(10, 60)  # 每用户每分钟 10 单
