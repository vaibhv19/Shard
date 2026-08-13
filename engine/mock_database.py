import threading


class MockDatabase:
    """
    A thread-safe simulated database wrapper for testing Write-Through and Write-Back semantics.
    """
    def __init__(self):
        self._db = {}
        self.lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self.lock:
            return self._db.get(key)

    def set(self, key: str, value: str) -> None:
        with self.lock:
            # Simulate a database write failure for testing error propagation
            if key == "simulate_db_failure":
                raise RuntimeError("Database write error")
            self._db[key] = value

    def clear(self) -> None:
        with self.lock:
            self._db.clear()
