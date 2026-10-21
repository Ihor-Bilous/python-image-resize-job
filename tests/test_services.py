import base64

import pytest

from app.exceptions import DownloadUnavailableError, RateLimitExceededError
from app.services.database import connect
from app.services.mailer import MailtrapMailer
from app.services.rate_limiter import RateLimiter
from app.types import ResizedImage

IMAGE = ResizedImage(b"png-bytes", 320, 160)


def test_store_creates_job_and_serves_image_by_token(store):
    job = store.create(IMAGE, "secret-token")

    assert job.email_status == "pending"
    assert store.get_image("secret-token") == b"png-bytes"
    with pytest.raises(DownloadUnavailableError):
        store.get_image("guess")


def test_expired_links_are_denied(store, db_path):
    store.create(IMAGE, "secret-token")
    with connect(db_path) as conn:
        conn.execute("UPDATE jobs SET expires_at = 0")

    with pytest.raises(DownloadUnavailableError):
        store.get_image("secret-token")


def test_email_status_is_recorded(store):
    job = store.create(IMAGE, "secret-token")
    store.set_email_status(job.id, "sent")

    assert [j.email_status for j in store.list_recent()] == ["sent"]


def test_recipient_limit_is_persistent_and_case_insensitive(db_path):
    for i in range(3):
        RateLimiter(db_path).check(f"client-{i}", "reader@example.com")

    with pytest.raises(RateLimitExceededError):
        RateLimiter(db_path).check("another-client", "READER@example.com")


def test_client_limit(db_path):
    limiter = RateLimiter(db_path)
    for i in range(12):
        limiter.check("client", f"reader{i}@example.com")

    with pytest.raises(RateLimitExceededError):
        limiter.check("client", "new@example.com")


def test_mailer_builds_mail_with_inline_preview(monkeypatch):
    sent = []

    class FakeClient:
        def __init__(self, **kwargs):
            sent.append(kwargs)

        def send(self, mail):
            sent.append(mail)

    monkeypatch.setattr("app.services.mailer.mt.MailtrapClient", FakeClient)

    MailtrapMailer().send_image_ready("job1", "reader@example.com", IMAGE, b"preview", "http://x/images/t")

    client_kwargs, mail = sent
    assert client_kwargs["sandbox"] is False
    assert mail.to[0].email == "reader@example.com"
    assert mail.custom_variables == {"job_id": "job1"}
    assert "cid:resize-preview" in mail.html
    assert mail.attachments[0].content_id == "resize-preview"
    payload = mail.api_data  # the real request body the SDK would POST
    assert base64.b64decode(payload["attachments"][0]["content"]) == b"preview"
    assert payload["attachments"][0]["disposition"] == "inline"
    assert "http://x/images/t" in mail.text
