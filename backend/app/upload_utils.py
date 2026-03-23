"""
Shared file upload validation utilities.
Validates file content via magic bytes and sanitizes filenames.
"""

import re

# Magic byte signatures mapped to MIME types
_MAGIC_SIGS: list[tuple[bytes, int, str]] = [
    # Images
    (b"\xff\xd8\xff", 0, "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", 0, "image/png"),
    # WebP: starts with RIFF....WEBP
    (b"WEBP", 8, "image/webp"),
    # Videos
    (b"ftyp", 4, "video/mp4"),       # MP4/MOV ftyp box
    (b"\x1a\x45\xdf\xa3", 0, "video/webm"),  # WebM/MKV EBML header
]


def detect_mime(header: bytes) -> str | None:
    """Detect MIME type from the first 12+ bytes of a file.
    Returns the MIME type string or None if unrecognized."""
    for sig, offset, mime in _MAGIC_SIGS:
        end = offset + len(sig)
        if len(header) >= end and header[offset:end] == sig:
            return mime
    return None


MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_magic_bytes(content: bytes, allowed_types: set[str]) -> str | None:
    """Return detected MIME type if it matches an allowed type, else None."""
    detected = detect_mime(content[:32])
    if detected and detected in allowed_types:
        return detected
    return None


def validate_file_size(content: bytes, max_bytes: int = MAX_UPLOAD_BYTES) -> None:
    """Raise ValueError if content exceeds max_bytes."""
    if len(content) > max_bytes:
        mb = max_bytes / (1024 * 1024)
        raise ValueError(f"File too large — maximum {mb:.0f} MB")


def sanitize_extension(
    filename: str | None,
    allowed_exts: set[str],
    default: str,
) -> str:
    """Extract and validate file extension.

    Only uses the final extension after the last dot and strips
    everything non-alphanumeric. This prevents double-extension attacks
    like 'shell.php.png' — only 'png' is extracted.
    """
    if not filename:
        return default
    # Only take the part after the LAST dot
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else default
    ext = re.sub(r"[^a-z0-9]", "", ext)
    return ext if ext in allowed_exts else default
