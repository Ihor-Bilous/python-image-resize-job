from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ResizedImage:
    data: bytes
    width: int
    height: int


@dataclass(frozen=True)
class JobRecord:
    id: str
    created_at: datetime
    email_status: str
