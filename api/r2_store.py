"""Private Cloudflare R2 object storage for thesis uploads and research results.

Credentials are loaded only from Render environment variables, never from
GitHub or the web UI. This uses the standard S3-compatible R2 endpoint.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

PREFIX = "thesis/research/"


def configured() -> bool:
    return all(os.getenv(name) for name in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"))


def _client():
    if not configured():
        raise RuntimeError("R2 credentials not configured in the server environment")
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=__import__("botocore.config", fromlist=["Config"]).Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=8,
            read_timeout=45,
        ),
    )


def _key(name: str) -> str:
    if not name or name.startswith("/") or "\\" in name or ".." in Path(name).parts:
        raise ValueError("Invalid R2 object path")
    return PREFIX + name


def put_bytes(name: str, payload: bytes, content_type: str = "application/octet-stream") -> None:
    _client().put_object(Bucket=os.environ["R2_BUCKET"], Key=_key(name),
                         Body=payload, ContentType=content_type,
                         CacheControl="private, no-store")


def get_bytes(name: str) -> bytes:
    return _client().get_object(Bucket=os.environ["R2_BUCKET"], Key=_key(name))["Body"].read()


def delete(name: str) -> None:
    _client().delete_object(Bucket=os.environ["R2_BUCKET"], Key=_key(name))


def exists(name: str) -> bool:
    from botocore.exceptions import ClientError
    try:
        _client().head_object(Bucket=os.environ["R2_BUCKET"], Key=_key(name))
        return True
    except ClientError as exc:
        if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
            return False
        raise


def list_names(prefix: str) -> list[str]:
    full_prefix = _key(prefix)
    paginator = _client().get_paginator("list_objects_v2")
    results: list[str] = []
    for page in paginator.paginate(Bucket=os.environ["R2_BUCKET"], Prefix=full_prefix):
        results.extend(obj["Key"][len(PREFIX):] for obj in page.get("Contents", []))
    return results


def put_json(name: str, data: dict) -> None:
    put_bytes(name, json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"), "application/json")


def get_json(name: str) -> dict:
    return json.loads(get_bytes(name).decode("utf-8"))


def upload_model_directory(directory: Path, exp_id: str) -> int:
    """Keep generated model checkpoints across Render restarts."""
    files = 0
    if directory.is_dir():
        for file in directory.rglob("*"):
            if file.is_file():
                put_bytes(f"models/{exp_id}/{file.relative_to(directory).as_posix()}", file.read_bytes())
                files += 1
    return files


def remove_model_directory(exp_id: str) -> None:
    for key in list_names(f"models/{exp_id}/"):
        delete(key)
