import os

os.environ.setdefault("MAILTRAP_API_TOKEN", "test-token")
os.environ.setdefault("MAILTRAP_SANDBOX", "false")
os.environ.setdefault("MAIL_FROM", "sender@example.com")
os.environ.setdefault("MAIL_FROM_NAME", "Test Sender")
os.environ.setdefault("ADMIN_PASSWORD", "test-password-long-enough")

from io import BytesIO  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.app import create_app  # noqa: E402
from app.dependencies import get_job_store, get_mailer, get_rate_limiter  # noqa: E402
from app.services.job_store import JobStore  # noqa: E402
from app.services.rate_limiter import RateLimiter  # noqa: E402


class FakeMailer:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.fail = False

    def send_image_ready(self, job_id, to_email, image, preview, download_url) -> None:
        if self.fail:
            raise RuntimeError("Mailtrap unavailable")
        self.sent.append(
            {"job_id": job_id, "to": to_email, "image": image, "preview": preview, "url": download_url}
        )


def make_png(size: tuple[int, int] = (800, 400)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (70, 130, 90)).save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def db_path(tmp_path) -> str:
    return str(tmp_path / "app.sqlite")


@pytest.fixture
def mailer() -> FakeMailer:
    return FakeMailer()


@pytest.fixture
def store(db_path) -> JobStore:
    return JobStore(db_path)


@pytest.fixture
def client(db_path, mailer, store) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_mailer] = lambda: mailer
    app.dependency_overrides[get_job_store] = lambda: store
    app.dependency_overrides[get_rate_limiter] = lambda: RateLimiter(db_path)
    return TestClient(app)
