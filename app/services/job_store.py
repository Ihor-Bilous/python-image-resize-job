import hashlib
import time
import uuid
from datetime import datetime, timezone

from app.exceptions import DownloadUnavailableError
from app.services.database import connect, init_db
from app.types import JobRecord, ResizedImage

LINK_TTL_SECONDS = 3600
_LIST_LIMIT = 50


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _to_record(row) -> JobRecord:
    return JobRecord(
        id=row["id"],
        created_at=datetime.fromtimestamp(row["created_at"], tz=timezone.utc),
        email_status=row["email_status"],
    )


class JobStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        init_db(db_path)

    def create(self, image: ResizedImage, token: str) -> JobRecord:
        job_id = uuid.uuid4().hex
        now = time.time()
        with connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO jobs (id, image, token_hash, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                (job_id, image.data, _hash_token(token), now, now + LINK_TTL_SECONDS),
            )
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _to_record(row)

    def get_image(self, token: str) -> bytes:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT image FROM jobs WHERE token_hash = ? AND expires_at > ?",
                (_hash_token(token), time.time()),
            ).fetchone()
        if row is None:
            raise DownloadUnavailableError("The image link is invalid or has expired.")
        return bytes(row["image"])

    def set_email_status(self, job_id: str, status: str) -> None:
        with connect(self._db_path) as conn:
            conn.execute("UPDATE jobs SET email_status = ? WHERE id = ?", (status, job_id))

    def list_recent(self) -> list[JobRecord]:
        with connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT id, created_at, email_status FROM jobs ORDER BY created_at DESC LIMIT ?",
                (_LIST_LIMIT,),
            ).fetchall()
        return [_to_record(row) for row in rows]
