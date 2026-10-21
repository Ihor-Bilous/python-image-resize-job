import logging

from app.protocols import JobStoreProtocol, MailerProtocol
from app.types import ResizedImage

logger = logging.getLogger(__name__)


def send_download_link(
    job_id: str,
    to_email: str,
    image: ResizedImage,
    preview: bytes,
    download_url: str,
    mailer: MailerProtocol,
    store: JobStoreProtocol,
) -> None:
    try:
        mailer.send_image_ready(job_id, to_email, image, preview, download_url)
    except Exception:
        logger.exception("Failed to send download link for job %s", job_id)
        store.set_email_status(job_id, "failed")
    else:
        store.set_email_status(job_id, "sent")
