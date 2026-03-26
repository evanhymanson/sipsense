"""
Migrate local uploads to S3.

Uploads all files from the local uploads/ directory to the configured S3 bucket
with correct content types and cache headers. Idempotent — skips files that
already exist in S3 with matching sizes.

Usage (run inside the backend Docker container on prod):
    python -m scripts.migrate_to_s3                        # full migration
    python -m scripts.migrate_to_s3 --dry-run              # preview only
    python -m scripts.migrate_to_s3 --verify-only          # check S3 vs local
    python -m scripts.migrate_to_s3 --subdir bottles_nobg  # migrate one subdir
    python -m scripts.migrate_to_s3 --subdir cocktails     # small test batch

Or pass credentials directly (without adding to .env):
    docker exec -e AWS_ACCESS_KEY_ID=AKIA... -e AWS_SECRET_ACCESS_KEY=... \\
      -it <backend-container> python -m scripts.migrate_to_s3 --dry-run
"""

import os
import sys
import argparse
import mimetypes
import logging
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from tqdm import tqdm

UPLOADS_ROOT = Path(__file__).resolve().parent.parent / "uploads"
BUCKET = os.environ.get("S3_BUCKET", "sipsense-media")
REGION = os.environ.get("AWS_REGION", "us-east-2")

MIME_OVERRIDES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
}

CACHE_CONTROL = "public, max-age=31536000, immutable"

log = logging.getLogger(__name__)


def get_content_type(filepath: Path) -> str:
    ext = filepath.suffix.lower()
    if ext in MIME_OVERRIDES:
        return MIME_OVERRIDES[ext]
    ct, _ = mimetypes.guess_type(str(filepath))
    return ct or "application/octet-stream"


def collect_local_files(root: Path, subdir: str | None = None) -> list[Path]:
    """Walk the uploads directory and return all files."""
    search_root = root / subdir if subdir else root
    if not search_root.exists():
        log.error("Directory not found: %s", search_root)
        sys.exit(1)
    files = []
    for path in sorted(search_root.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            files.append(path)
    return files


def s3_key_for(filepath: Path, uploads_root: Path) -> str:
    """Convert local path to S3 key: uploads/bottles/X.png"""
    relative = filepath.relative_to(uploads_root)
    return f"uploads/{relative}"


def object_matches(s3_client, bucket: str, key: str, local_size: int) -> bool:
    """Check if S3 object exists with matching size."""
    try:
        resp = s3_client.head_object(Bucket=bucket, Key=key)
        return resp["ContentLength"] == local_size
    except ClientError:
        return False


def upload_files(
    files: list[Path],
    uploads_root: Path,
    s3_client,
    bucket: str,
    dry_run: bool = False,
) -> dict:
    stats = {"uploaded": 0, "skipped": 0, "errors": 0, "bytes": 0}

    with tqdm(total=len(files), desc="Uploading", unit="file") as pbar:
        for filepath in files:
            key = s3_key_for(filepath, uploads_root)
            local_size = filepath.stat().st_size
            content_type = get_content_type(filepath)

            if object_matches(s3_client, bucket, key, local_size):
                stats["skipped"] += 1
                pbar.update(1)
                continue

            if dry_run:
                tqdm.write(
                    f"  [DRY RUN] {key}  ({local_size:,} bytes, {content_type})"
                )
                stats["uploaded"] += 1
                pbar.update(1)
                continue

            try:
                s3_client.upload_file(
                    str(filepath),
                    bucket,
                    key,
                    ExtraArgs={
                        "ContentType": content_type,
                        "CacheControl": CACHE_CONTROL,
                    },
                )
                stats["uploaded"] += 1
                stats["bytes"] += local_size
            except Exception as exc:
                log.error("Failed to upload %s: %s", key, exc)
                stats["errors"] += 1

            pbar.update(1)

    return stats


def verify_uploads(
    files: list[Path],
    uploads_root: Path,
    s3_client,
    bucket: str,
) -> tuple[list[str], list[tuple[str, int, int]]]:
    missing: list[str] = []
    size_mismatch: list[tuple[str, int, int]] = []

    with tqdm(total=len(files), desc="Verifying", unit="file") as pbar:
        for filepath in files:
            key = s3_key_for(filepath, uploads_root)
            local_size = filepath.stat().st_size

            try:
                resp = s3_client.head_object(Bucket=bucket, Key=key)
                if resp["ContentLength"] != local_size:
                    size_mismatch.append((key, local_size, resp["ContentLength"]))
            except ClientError:
                missing.append(key)

            pbar.update(1)

    return missing, size_mismatch


def print_summary(stats: dict) -> None:
    print(f"\n{'=' * 50}")
    print(f"  Uploaded:  {stats['uploaded']:,}")
    print(f"  Skipped:   {stats['skipped']:,}")
    print(f"  Errors:    {stats['errors']:,}")
    if stats["bytes"]:
        gb = stats["bytes"] / (1024**3)
        print(f"  Transferred: {gb:.2f} GB")
    print(f"{'=' * 50}")


def print_verify_results(
    missing: list[str], size_mismatch: list[tuple[str, int, int]]
) -> None:
    if not missing and not size_mismatch:
        print("\nVerification PASSED — all files present in S3 with correct sizes.")
        return

    if missing:
        print(f"\nWARNING: {len(missing)} files MISSING from S3:")
        for key in missing[:20]:
            print(f"  - {key}")
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more")

    if size_mismatch:
        print(f"\nWARNING: {len(size_mismatch)} files with SIZE MISMATCH:")
        for key, local, remote in size_mismatch[:20]:
            print(f"  - {key}  local={local:,}  s3={remote:,}")
        if len(size_mismatch) > 20:
            print(f"  ... and {len(size_mismatch) - 20} more")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate local uploads to S3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without uploading")
    parser.add_argument("--verify-only", action="store_true", help="Only verify S3 vs local")
    parser.add_argument("--subdir", type=str, help="Only migrate a specific subdirectory (e.g. bottles_nobg, cocktails)")
    parser.add_argument("--bucket", type=str, default=BUCKET, help=f"S3 bucket name (default: {BUCKET})")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not UPLOADS_ROOT.exists():
        print(f"ERROR: uploads directory not found: {UPLOADS_ROOT}")
        sys.exit(1)

    s3 = boto3.client("s3", region_name=REGION)

    # Quick credential check
    try:
        s3.head_bucket(Bucket=args.bucket)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "403":
            print(f"ERROR: Access denied to bucket '{args.bucket}'. Check AWS credentials.")
        elif code == "404":
            print(f"ERROR: Bucket '{args.bucket}' does not exist.")
        else:
            print(f"ERROR: Cannot access bucket '{args.bucket}': {exc}")
        sys.exit(1)

    files = collect_local_files(UPLOADS_ROOT, args.subdir)
    total_size = sum(f.stat().st_size for f in files)
    print(f"Found {len(files):,} files in {UPLOADS_ROOT / (args.subdir or '')}")
    print(f"Total size: {total_size / (1024**3):.2f} GB")
    print(f"Target bucket: {args.bucket}")
    print()

    if args.verify_only:
        missing, mismatches = verify_uploads(files, UPLOADS_ROOT, s3, args.bucket)
        print_verify_results(missing, mismatches)
        sys.exit(1 if missing or mismatches else 0)

    stats = upload_files(files, UPLOADS_ROOT, s3, args.bucket, dry_run=args.dry_run)
    print_summary(stats)

    if not args.dry_run and stats["errors"] == 0:
        print("\nRunning verification pass...")
        missing, mismatches = verify_uploads(files, UPLOADS_ROOT, s3, args.bucket)
        print_verify_results(missing, mismatches)
        sys.exit(1 if missing or mismatches else 0)
    elif stats["errors"] > 0:
        print("\nSkipping verification due to upload errors. Fix errors and re-run.")
        sys.exit(1)


if __name__ == "__main__":
    main()
