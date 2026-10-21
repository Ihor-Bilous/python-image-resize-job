from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.exceptions import ImageTooLargeError, InvalidImageError
from app.types import ResizedImage

MAX_UPLOAD_BYTES = 4 * 1024 * 1024
MAX_PIXELS = 8_000_000
_ALLOWED_FORMATS = {"JPEG", "PNG"}
_PREVIEW_SIZE = 160


class ImageResizeService:
    def resize(self, data: bytes, max_side: int) -> ResizedImage:
        if len(data) > MAX_UPLOAD_BYTES:
            raise ImageTooLargeError("Choose an image no larger than 4 MiB.")
        try:
            with Image.open(BytesIO(data)) as source:
                if source.format not in _ALLOWED_FORMATS or getattr(source, "n_frames", 1) != 1:
                    raise InvalidImageError("Use a single-frame JPEG or PNG.")
                if source.width * source.height > MAX_PIXELS:
                    raise InvalidImageError("Use an image under 8 megapixels.")
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise InvalidImageError("The image cannot be decoded; use a valid JPEG or PNG.") from exc

        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        image.info.clear()
        return ResizedImage(_encode_png(image), *image.size)

    def preview(self, data: bytes) -> bytes:
        with Image.open(BytesIO(data)) as image:
            image.thumbnail((_PREVIEW_SIZE, _PREVIEW_SIZE))
            return _encode_png(image)


def _encode_png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()
