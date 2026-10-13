"""ROS images to the bytes the API reads (JPEG, PNG or WebP)."""

import io
from typing import Any

# encoding -> (Pillow mode of the data, bytes per pixel)
RAW_ENCODINGS = {
    "rgb8": ("RGB", 3),
    "bgr8": ("BGR", 3),
    "rgba8": ("RGBA", 4),
    "bgra8": ("BGRA", 4),
    "mono8": ("L", 1),
}
COMPRESSED_FORMATS = ("jpeg", "jpg", "png", "webp")


class ImageError(ValueError):
    """A ROS image this node cannot turn into a JPEG, PNG or WebP."""


def compressed_bytes(fmt: str, data: Any) -> bytes:
    """A sensor_msgs/CompressedImage's bytes, sent as they are."""
    kind = (fmt or "").lower()
    if not any(f in kind for f in COMPRESSED_FORMATS):
        raise ImageError("compressed image format %r is not JPEG, PNG or WebP" % fmt)
    return bytes(data)


def raw_to_jpeg(encoding: str, width: int, height: int, step: int, data: Any, quality: int = 85) -> bytes:
    """A sensor_msgs/Image (rgb8, bgr8, rgba8, bgra8 or mono8) encoded as a JPEG."""
    from PIL import Image as PILImage

    if encoding not in RAW_ENCODINGS:
        raise ImageError("image encoding %r is not one of %s" % (encoding, ", ".join(sorted(RAW_ENCODINGS))))
    mode, bpp = RAW_ENCODINGS[encoding]
    if width <= 0 or height <= 0:
        raise ImageError("image is %dx%d pixels" % (width, height))
    row = width * bpp
    step = step or row
    raw = bytes(data)
    if step < row or len(raw) < step * (height - 1) + row:
        raise ImageError("image data is %d bytes, too short for %dx%d %s" % (len(raw), width, height, encoding))
    if step != row:
        # Rows padded to step bytes: keep each row's pixels only.
        raw = b"".join(raw[i * step:i * step + row] for i in range(height))
    target = {"BGR": "RGB", "BGRA": "RGBA"}.get(mode, mode)
    pixels = PILImage.frombytes(target, (width, height), raw[: row * height], "raw", mode)
    if pixels.mode not in ("RGB", "L"):
        pixels = pixels.convert("RGB")
    out = io.BytesIO()
    pixels.save(out, format="JPEG", quality=int(quality))
    return out.getvalue()
