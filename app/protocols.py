from typing import Protocol

from app.types import JobRecord, ResizedImage


class ImageServiceProtocol(Protocol):
    def resize(self, data: bytes, max_side: int) -> ResizedImage: ...

    def preview(self, data: bytes) -> bytes: ...


class JobStoreProtocol(Protocol):
    def create(self, image: ResizedImage, token: str) -> JobRecord: ...

    def get_image(self, token: str) -> bytes: ...

    def set_email_status(self, job_id: str, status: str) -> None: ...

    def list_recent(self) -> list[JobRecord]: ...


class RateLimiterProtocol(Protocol):
    def check(self, client_id: str, recipient: str) -> None: ...


class MailerProtocol(Protocol):
    def send_image_ready(
        self,
        job_id: str,
        to_email: str,
        image: ResizedImage,
        preview: bytes,
        download_url: str,
    ) -> None: ...
