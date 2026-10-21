import secrets
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import get_settings
from app.services.image_service import ImageResizeService
from app.services.job_store import JobStore
from app.services.mailer import MailtrapMailer
from app.services.rate_limiter import RateLimiter

_MIN_ADMIN_PASSWORD_LENGTH = 16

_basic_auth = HTTPBasic(realm="Operator")


@lru_cache(maxsize=1)
def get_image_service() -> ImageResizeService:
    return ImageResizeService()


@lru_cache(maxsize=1)
def get_job_store() -> JobStore:
    return JobStore(get_settings().db_path)


@lru_cache(maxsize=1)
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_settings().db_path)


@lru_cache(maxsize=1)
def get_mailer() -> MailtrapMailer:
    return MailtrapMailer()


def require_admin(credentials: Annotated[HTTPBasicCredentials, Depends(_basic_auth)]) -> None:
    password = get_settings().admin_password
    if len(password) < _MIN_ADMIN_PASSWORD_LENGTH:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Set ADMIN_PASSWORD to a random value of at least 16 characters.",
        )
    valid = secrets.compare_digest(credentials.username.encode(), b"admin") & secrets.compare_digest(
        credentials.password.encode(), password.encode()
    )
    if not valid:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Operator sign-in required.",
            headers={"WWW-Authenticate": 'Basic realm="Operator"'},
        )
