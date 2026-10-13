import pytest

from decisionnode_ros.images import ImageError, compressed_bytes, raw_to_jpeg

JPEG = b"\xff\xd8\xff"


@pytest.mark.parametrize("encoding, bpp", [("rgb8", 3), ("bgr8", 3), ("rgba8", 4), ("bgra8", 4), ("mono8", 1)])
def test_raw_encodings_become_jpeg(encoding, bpp):
    width, height = 4, 3
    data = bytes(range(256))[: width * height * bpp] * 1
    assert raw_to_jpeg(encoding, width, height, width * bpp, data).startswith(JPEG)


def test_padded_rows():
    width, height, step = 3, 2, 12  # 9 bytes of pixels per row, 3 of padding
    data = (b"\x10" * 9 + b"\x00" * 3) * height
    assert raw_to_jpeg("rgb8", width, height, step, data).startswith(JPEG)


def test_bgr_is_turned_into_rgb():
    from io import BytesIO

    from PIL import Image

    jpeg = raw_to_jpeg("bgr8", 8, 8, 24, b"\x00\x00\xff" * 64, quality=100)  # pure red in BGR
    r, g, b = Image.open(BytesIO(jpeg)).convert("RGB").getpixel((4, 4))
    assert r > 200 and g < 50 and b < 50


@pytest.mark.parametrize("args, words", [
    (("yuv422", 2, 2, 4, b"\x00" * 8), "is not one of"),
    (("rgb8", 0, 2, 0, b""), "pixels"),
    (("rgb8", 4, 4, 12, b"\x00" * 10), "too short"),
])
def test_bad_raw_images(args, words):
    with pytest.raises(ImageError, match=words):
        raw_to_jpeg(*args)


def test_compressed_images_pass_through():
    assert compressed_bytes("jpeg", b"\xff\xd8\xffdata") == b"\xff\xd8\xffdata"
    assert compressed_bytes("rgb8; png compressed bgr8", b"\x89PNG") == b"\x89PNG"
    with pytest.raises(ImageError):
        compressed_bytes("tiff", b"II*")
