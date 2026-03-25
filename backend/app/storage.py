"""
Unified storage layer: S3 + CloudFront in production, local disk in development.

When S3_BUCKET env var is set, files are uploaded to S3 and URLs point to the
CDN_BASE_URL (CloudFront).  When unset, everything falls back to local disk
and /uploads/ paths — so local dev works unchanged.
"""

import os
import logging

logger = logging.getLogger(__name__)

# Configuration from environment
S3_BUCKET = os.getenv("S3_BUCKET")  # e.g. "sipsense-media"
CDN_BASE_URL = (os.getenv("CDN_BASE_URL") or "").rstrip("/")
AWS_REGION = os.getenv("AWS_REGION", "us-east-2")

_UPLOADS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))

_s3_client = None


def _get_s3():
    global _s3_client
    if _s3_client is None and S3_BUCKET:
        import boto3
        _s3_client = boto3.client("s3", region_name=AWS_REGION)
    return _s3_client


def is_s3_enabled() -> bool:
    return bool(S3_BUCKET)


def upload_file(local_path: str, s3_key: str, content_type: str | None = None) -> str:
    """Upload a local file to S3.  Returns the CDN URL (or local path in dev)."""
    s3 = _get_s3()
    if not s3:
        return f"/uploads/{s3_key}"

    extra = {}
    if content_type:
        extra["ContentType"] = content_type

    s3.upload_file(local_path, S3_BUCKET, f"uploads/{s3_key}", ExtraArgs=extra)
    return f"{CDN_BASE_URL}/uploads/{s3_key}"


def upload_bytes(data: bytes, s3_key: str, content_type: str | None = None) -> str:
    """Upload raw bytes to S3.  Returns the CDN URL (or local path in dev)."""
    s3 = _get_s3()
    if not s3:
        return f"/uploads/{s3_key}"

    extra = {}
    if content_type:
        extra["ContentType"] = content_type

    s3.put_object(Bucket=S3_BUCKET, Key=f"uploads/{s3_key}", Body=data, **extra)
    return f"{CDN_BASE_URL}/uploads/{s3_key}"


def file_exists_local(relative_path: str) -> bool:
    """Check if a file exists on local disk (for dev / cache building)."""
    return os.path.isfile(os.path.join(_UPLOADS_ROOT, relative_path))


def make_cdn_url(path: str | None) -> str | None:
    """Convert a /uploads/... path to a full CDN URL.  Pass-through in dev."""
    if not path:
        return path
    if path.startswith("http"):
        return path
    if not CDN_BASE_URL:
        return path
    clean = path.lstrip("/")
    return f"{CDN_BASE_URL}/{clean}"


# ── Cached image sets (built once at startup) ───────────────────────────

_nobg_set: set[str] | None = None
_pairing_set: set[str] | None = None
_cocktail_set: set[str] | None = None


def _load_file_set(subdir: str) -> set[str]:
    """List filenames in an uploads subdirectory (local or S3)."""
    if is_s3_enabled():
        s3 = _get_s3()
        result = set()
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=f"uploads/{subdir}/"):
            for obj in page.get("Contents", []):
                result.add(obj["Key"].split("/")[-1])
        return result

    local_dir = os.path.join(_UPLOADS_ROOT, subdir)
    if os.path.isdir(local_dir):
        return set(os.listdir(local_dir))
    return set()


def get_nobg_set() -> set[str]:
    global _nobg_set
    if _nobg_set is None:
        _nobg_set = _load_file_set("bottles_nobg")
        logger.info("Cached %d bottles_nobg filenames", len(_nobg_set))
    return _nobg_set


def get_pairing_set() -> set[str]:
    global _pairing_set
    if _pairing_set is None:
        _pairing_set = _load_file_set("pairings")
        logger.info("Cached %d pairing image filenames", len(_pairing_set))
    return _pairing_set


def get_cocktail_set() -> set[str]:
    global _cocktail_set
    if _cocktail_set is None:
        _cocktail_set = _load_file_set("cocktails")
        logger.info("Cached %d cocktail image filenames", len(_cocktail_set))
    return _cocktail_set
