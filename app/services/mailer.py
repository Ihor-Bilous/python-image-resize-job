import base64
import logging
from pathlib import Path

import mailtrap as mt
from jinja2 import Environment, FileSystemLoader

from app.config import get_settings
from app.types import ResizedImage

logger = logging.getLogger(__name__)

_PREVIEW_CONTENT_ID = "resize-preview"

_email_templates = Environment(
    loader=FileSystemLoader(Path(__file__).parent.parent.parent / "templates" / "email"),
    autoescape=True,
)


class MailtrapMailer:
    def send_image_ready(
        self,
        job_id: str,
        to_email: str,
        image: ResizedImage,
        preview: bytes,
        download_url: str,
    ) -> None:
        settings = get_settings()
        context = {
            "width": image.width,
            "height": image.height,
            "download_url": download_url,
            "preview_cid": _PREVIEW_CONTENT_ID,
        }
        mail = mt.Mail(
            sender=mt.Address(email=settings.mail_from, name=settings.mail_from_name),
            to=[mt.Address(email=to_email)],
            subject="Your resized image is ready",
            text=(
                f"Download your {image.width} × {image.height} image:\n{download_url}\n\n"
                "This private link expires in one hour."
            ),
            html=_email_templates.get_template("image_ready.html").render(**context),
            category="image-ready",
            custom_variables={"job_id": job_id},
            attachments=[
                mt.Attachment(
                    content=base64.b64encode(preview),  # the SDK expects base64-encoded bytes
                    filename="preview.png",
                    mimetype="image/png",
                    disposition=mt.Disposition.INLINE,
                    content_id=_PREVIEW_CONTENT_ID,
                )
            ],
        )
        client = mt.MailtrapClient(
            token=settings.mailtrap_api_token,
            sandbox=settings.mailtrap_sandbox,
            inbox_id=settings.mailtrap_inbox_id or None,
        )
        client.send(mail)
        logger.info("Download link for job %s sent", job_id)
