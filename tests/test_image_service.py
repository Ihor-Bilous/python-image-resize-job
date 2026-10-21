from io import BytesIO

import pytest
from PIL import Image

from app.exceptions import ImageTooLargeError, InvalidImageError
from app.services import image_service
from app.services.image_service import ImageResizeService
from tests.conftest import make_png

service = ImageResizeService()


def test_resize_keeps_aspect_ratio_and_never_enlarges():
    resized = service.resize(make_png((800, 400)), 320)
    assert (resized.width, resized.height) == (320, 160)

    small = service.resize(make_png((100, 50)), 640)
    assert (small.width, small.height) == (100, 50)


def test_output_does_not_keep_source_metadata():
    exif = Image.Exif()
    exif[315] = "Private test author"
    source = BytesIO()
    Image.new("RGB", (100, 100)).save(source, "PNG", exif=exif)

    resized = service.resize(source.getvalue(), 64)

    assert not Image.open(BytesIO(resized.data)).getexif()


def test_rejects_non_images_and_wrong_formats():
    with pytest.raises(InvalidImageError):
        service.resize(b"not an image", 320)

    gif = BytesIO()
    Image.new("RGB", (10, 10)).save(gif, "GIF")
    with pytest.raises(InvalidImageError):
        service.resize(gif.getvalue(), 320)


def test_rejects_oversized_uploads_and_pixel_bombs(monkeypatch):
    with pytest.raises(ImageTooLargeError):
        service.resize(b"0" * (image_service.MAX_UPLOAD_BYTES + 1), 320)

    monkeypatch.setattr(image_service, "MAX_PIXELS", 10)
    with pytest.raises(InvalidImageError, match="megapixels"):
        service.resize(make_png(), 320)


def test_preview_is_bounded():
    preview = service.preview(make_png((800, 400)))
    assert Image.open(BytesIO(preview)).size == (160, 80)
