import hashlib
import time

from app.exceptions import RateLimitExceededError
from app.services.database import connect, init_db

_WINDOW_SECONDS = 3600
_CLIENT_LIMIT = 12
_RECIPIENT_LIMIT = 3


def _key(scope: str, value: str) -> str:
    return hashlib.sha256(f"{scope}:{value}".encode()).hexdigest()


class RateLimiter:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        init_db(db_path)

    def check(self, client_id: str, recipient: str) -> None:
        now = time.time()
        limits = [
            (_key("client", client_id), _CLIENT_LIMIT),
            (_key("recipient", recipient.lower()), _RECIPIENT_LIMIT),
        ]
        with connect(self._db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM rate_limits WHERE expires_at <= ?", (now,))
            for key, limit in limits:
                row = conn.execute("SELECT count FROM rate_limits WHERE key = ?", (key,)).fetchone()
                if row and row["count"] >= limit:
                    raise RateLimitExceededError("Too many requests. Try again after the one-hour window.")
                conn.execute(
                    "INSERT INTO rate_limits (key, count, expires_at) VALUES (?, 1, ?) "
                    "ON CONFLICT(key) DO UPDATE SET count = count + 1",
                    (key, now + _WINDOW_SECONDS),
                )
