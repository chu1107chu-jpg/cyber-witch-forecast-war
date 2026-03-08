"""Cloudflare R2 (S3-совместимое) — upload/presigned URL."""
import logging
import os
from pathlib import Path

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)

_s3_client = None


def _get_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=os.environ["R2_ENDPOINT_URL"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
    return _s3_client


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload raw bytes → R2. Returns public URL."""
    bucket = os.environ.get("R2_BUCKET", "lichu-media")
    _get_client().put_object(
        Bucket=bucket, Key=key, Body=data,
        ContentType=content_type,
    )
    public_base = os.environ.get("R2_PUBLIC_URL", "").rstrip("/")
    return f"{public_base}/{key}"


def upload_file(local_path: str | Path, key: str) -> str:
    """Upload local file → R2."""
    bucket = os.environ.get("R2_BUCKET", "lichu-media")
    content_type = "application/octet-stream"
    _get_client().upload_file(str(local_path), bucket, key,
                              ExtraArgs={"ContentType": content_type})
    public_base = os.environ.get("R2_PUBLIC_URL", "").rstrip("/")
    return f"{public_base}/{key}"


def presigned_upload_url(key: str, expires: int = 3600) -> str:
    """Генерирует presigned URL для загрузки из браузера."""
    bucket = os.environ.get("R2_BUCKET", "lichu-media")
    return _get_client().generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )
