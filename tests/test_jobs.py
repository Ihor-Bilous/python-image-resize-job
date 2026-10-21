import base64
from io import BytesIO

from PIL import Image

from tests.conftest import make_png


def _post_job(client, email="reader@example.com", width="320", image=None):
    files = {"image": ("sample.png", image if image is not None else make_png(), "image/png")}
    return client.post("/jobs", data={"email": email, "width": width}, files=files, follow_redirects=False)


def test_job_resizes_emails_link_and_serves_private_download(client, mailer, store):
    response = _post_job(client)

    assert response.status_code == 303
    assert response.headers["location"] == "/success"
    [message] = mailer.sent
    assert message["to"] == "reader@example.com"
    assert (message["image"].width, message["image"].height) == (320, 160)
    assert Image.open(BytesIO(message["preview"])).size == (160, 80)
    assert [job.email_status for job in store.list_recent()] == ["sent"]

    token = message["url"].rsplit("/", 1)[1]
    download = client.get(f"/images/{token}")
    assert download.status_code == 200
    assert Image.open(BytesIO(download.content)).size == (320, 160)
    assert client.get("/images/guess").status_code == 410


def test_email_failure_is_recorded_and_request_is_kept(client, mailer, store):
    mailer.fail = True

    assert _post_job(client).status_code == 303
    assert [job.email_status for job in store.list_recent()] == ["failed"]


def test_invalid_input_is_rejected_without_sending(client, mailer):
    assert _post_job(client, image=b"not an image").status_code == 400
    assert _post_job(client, width="0").status_code == 422
    assert _post_job(client, email="invalid").status_code == 422
    assert client.post("/jobs", data={"email": "reader@example.com", "width": "320"}).status_code == 422
    assert mailer.sent == []


def test_recipient_is_rate_limited(client):
    for _ in range(3):
        assert _post_job(client).status_code == 303
    assert _post_job(client).status_code == 429


def test_admin_requires_credentials(client):
    assert client.get("/admin").status_code == 401
    wrong = {"Authorization": "Basic " + base64.b64encode(b"admin:wrong").decode()}
    assert client.get("/admin", headers=wrong).status_code == 401

    valid = {"Authorization": "Basic " + base64.b64encode(b"admin:test-password-long-enough").decode()}
    _post_job(client)
    page = client.get("/admin", headers=valid)
    assert page.status_code == 200
    assert "sent" in page.text
    assert "reader@example.com" not in page.text
