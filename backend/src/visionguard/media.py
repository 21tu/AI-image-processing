import hashlib
import warnings
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps


class UnsupportedMediaType(ValueError):
    pass


class InvalidImage(ValueError):
    pass


class ImageTooLarge(InvalidImage):
    pass


@dataclass(frozen=True)
class SanitizedImage:
    data: bytes
    mime: str
    ext: str
    width: int
    height: int
    sha256: str


def sniff_mime(head: bytes) -> str:
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    raise UnsupportedMediaType()


def sanitize_image(data: bytes, *, max_pixels: int) -> SanitizedImage:
    mime = sniff_mime(data[:32])
    fmt, ext = {
        "image/jpeg": ("JPEG", "jpg"),
        "image/png": ("PNG", "png"),
        "image/webp": ("WEBP", "webp"),
    }[mime]
    try:
        # Never mutate Pillow's process-global limits or truncated-image settings.
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.width * source.height > max_pixels:
                    raise ImageTooLarge()
                if source.format != fmt or getattr(source, "n_frames", 1) != 1:
                    raise InvalidImage()
                source.verify()
            with Image.open(BytesIO(data)) as source:
                source.load()
                oriented = ImageOps.exif_transpose(source)
                mode = (
                    "RGB"
                    if fmt == "JPEG"
                    else "RGBA"
                    if "A" in oriented.getbands() or "transparency" in oriented.info
                    else "RGB"
                )
                converted = oriented.convert(mode)
                # A new pixel-only image prevents info/EXIF/ICC/XMP propagation.
                clean = Image.frombytes(mode, converted.size, converted.tobytes())
                output = BytesIO()
                options = (
                    {"quality": 95}
                    if fmt == "JPEG"
                    else {"lossless": True}
                    if fmt == "WEBP"
                    else {}
                )
                clean.save(output, format=fmt, **options)
                result = output.getvalue()
                return SanitizedImage(
                    result,
                    mime,
                    ext,
                    clean.width,
                    clean.height,
                    hashlib.sha256(result).hexdigest(),
                )
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageTooLarge() from exc
    except InvalidImage:
        raise
    except Exception as exc:
        raise InvalidImage() from exc
