# Image Resize Job

A FastAPI application that accepts a JPEG or PNG upload, resizes it into a bounded square without stretching, and emails the sender a private, expiring download link with an inline preview — all via the [Mailtrap](https://mailtrap.io) Python SDK.

## How It Works

```
Visitor submits the upload form
        │
        ▼
POST /jobs
        │
        ├─ Validate email + max side (Pydantic)
        ├─ Check rate limits (per client and per recipient)
        ├─ Decode, validate and resize with Pillow (PNG output, metadata stripped)
        ├─ Store image + hashed download token in SQLite (1h expiry)
        ├─ Send email with preview and download link  (background task)
        │       └─ Record email status: sent | failed
        └─ Redirect to /success

GET /images/{token} ── valid? → PNG download · expired/unknown → 410
```

## Features

- Pillow decodes the real file (never trusts the extension), applies EXIF orientation, rejects animated images and anything over 4 MiB or 8 megapixels
- Output is always a re-encoded PNG without source metadata; images are never enlarged
- Download links use a random token; only its SHA-256 hash is stored, and links expire after one hour
- Email contains an inline `cid:` preview image, a plain-text part, an `image-ready` category and a `job_id` custom variable for correlating Mailtrap logs
- Rate limits persisted in SQLite: 12 requests per client and 3 per recipient per hour
- `/admin` (HTTP Basic) lists job references and email status without exposing images or addresses
- Email failures are isolated in a background task and recorded as `failed`; they never break the upload response

## Prerequisites

- Python 3.12+
- [Mailtrap](https://mailtrap.io) account with an API token — a Sandbox inbox for development, or a verified sending domain for live delivery

## Setup

1. **Clone and enter the project directory**
   ```bash
   git clone https://github.com/Ihor-Bilous/mailtrap-python-examples.git
   cd mailtrap-python-examples/fastapi-image-resize-job
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and fill in all required values (see table below).

5. **Run the app**
   ```bash
   uvicorn main:app --reload
   ```
   The app is available at [http://localhost:8000](http://localhost:8000).

## Environment Variables

| Variable | Description |
|---|---|
| `MAILTRAP_API_TOKEN` | Mailtrap API token (Sandbox or Email Sending, matching `MAILTRAP_SANDBOX`) |
| `MAILTRAP_SANDBOX` | `true` captures emails in a Sandbox inbox (default); `false` sends real emails |
| `MAILTRAP_INBOX_ID` | Numeric inbox ID from the Sandbox API tab (required when `MAILTRAP_SANDBOX=true`) |
| `MAIL_FROM` | Sender email (must belong to a verified domain for live sending) |
| `MAIL_FROM_NAME` | Sender display name |
| `APP_URL` | Public origin used in emailed download links (default: `http://localhost:8000`) |
| `DB_PATH` | SQLite file path (default: `.data/app.sqlite`) |
| `ADMIN_PASSWORD` | Password for `/admin` (username `admin`); 16+ random characters. `/admin` returns 503 until set |

## Email Configuration

**Development (Sandbox)** — keep `MAILTRAP_SANDBOX=true`, set `MAILTRAP_API_TOKEN`, `MAILTRAP_INBOX_ID` and `MAIL_FROM`. Messages are captured in your Sandbox inbox and never reach real recipients. Find the inbox ID on the inbox's **API** tab.

**Production** — verify your sending domain in Mailtrap, set `MAILTRAP_SANDBOX=false`, `MAIL_FROM` on that domain and an Email Sending API token in `MAILTRAP_API_TOKEN`. Restart after changing configuration.

Each email carries the `image-ready` category and a `job_id` custom variable, which matches the reference shown in `/admin`.

## Flows

### Resize Request
1. Visit `/` and enter an email, a maximum side (64–1600 px) and a JPEG or PNG.
2. The image is resized, stored, and the page redirects to `/success`.
3. The email arrives with a preview and a download link valid for one hour.

### Email Status
`pending` → `sent` (accepted by Mailtrap's API — not a delivery guarantee) or `failed` (see the application log). The saved job is kept either way; failed sends are not retried automatically.

### Rate Limiting
Requests are counted per client IP and per recipient address. Forwarded-IP headers are ignored, so behind a reverse proxy all clients share one limit — add proxy-level limits before handling real traffic.

## Project Structure

```
fastapi-image-resize-job/
├── app/
│   ├── app.py              # FastAPI factory, error handler, security headers
│   ├── config.py           # Pydantic-settings config
│   ├── dependencies.py     # lru_cache singletons for FastAPI Depends + admin auth
│   ├── exceptions.py       # JobError hierarchy with HTTP status codes
│   ├── protocols.py        # Structural interfaces (ImageService, JobStore, RateLimiter, Mailer)
│   ├── schemas.py          # JobFormSchema (Pydantic)
│   ├── templates.py        # Shared Jinja2Templates instance
│   ├── types.py            # ResizedImage, JobRecord dataclasses
│   ├── routers/
│   │   ├── job_router.py       # GET /, POST /jobs, GET /success, GET /images/{token}
│   │   └── admin_router.py     # GET /admin (HTTP Basic)
│   ├── services/
│   │   ├── database.py         # SQLite schema + connection helper
│   │   ├── image_service.py    # ImageResizeService (Pillow)
│   │   ├── job_store.py        # JobStore (images, token hashes, email status)
│   │   ├── mailer.py           # MailtrapMailer
│   │   └── rate_limiter.py     # RateLimiter
│   └── use_cases/
│       └── send_download_link.py   # Send email and record sent/failed
├── templates/
│   ├── email/
│   │   └── image_ready.html    # Download-link email
│   └── pages/
│       ├── base.html
│       ├── index.html          # Upload form
│       ├── success.html
│       └── admin.html
├── tests/
├── main.py
├── requirements.txt
└── .env.example
```

## Key Integration Points

**Safe image decoding and resizing**

```python
with Image.open(BytesIO(data)) as source:
    if source.format not in {"JPEG", "PNG"} or getattr(source, "n_frames", 1) != 1:
        raise InvalidImageError("Use a single-frame JPEG or PNG.")
    if source.width * source.height > MAX_PIXELS:
        raise InvalidImageError("Use an image under 8 megapixels.")
    source.load()
    image = ImageOps.exif_transpose(source).convert("RGB")

image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
image.info.clear()  # drop source metadata
```

**Hashed, expiring download token**

```python
token = secrets.token_urlsafe(32)          # emailed to the recipient
token_hash = hashlib.sha256(token.encode()).hexdigest()   # the only thing stored
# lookup: WHERE token_hash = ? AND expires_at > now
```

**Email with an inline preview via the Mailtrap SDK**

```python
mail = mt.Mail(
    sender=mt.Address(email=settings.mail_from, name=settings.mail_from_name),
    to=[mt.Address(email=to_email)],
    subject="Your resized image is ready",
    text=text,
    html=html,  # <img src="cid:resize-preview">
    category="image-ready",
    custom_variables={"job_id": job_id},
    attachments=[
        mt.Attachment(
            content=preview,
            filename="preview.png",
            mimetype="image/png",
            disposition=mt.Disposition.INLINE,
            content_id="resize-preview",
        )
    ],
)
mt.MailtrapClient(
    token=settings.mailtrap_api_token,
    sandbox=settings.mailtrap_sandbox,
    inbox_id=settings.mailtrap_inbox_id or None,
).send(mail)
```

**Isolated email failures**

```python
try:
    mailer.send_image_ready(job_id, to_email, image, preview, download_url)
except Exception:
    logger.exception("Failed to send download link for job %s", job_id)
    store.set_email_status(job_id, "failed")
else:
    store.set_email_status(job_id, "sent")
```

## Tests

```bash
python -m pytest -q
```

Tests use fake mailers and temporary SQLite files; no Mailtrap account is needed.
