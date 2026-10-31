from __future__ import annotations

import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from minio import Minio

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    endpoint = urlparse(settings.minio_internal_endpoint)
    client = Minio(
        endpoint.netloc,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=endpoint.scheme == "https",
    )
    buckets = (
        settings.minio_bucket_assets,
        settings.minio_bucket_artifacts,
        settings.minio_bucket_output,
    )
    for attempt in range(30):
        try:
            for bucket in buckets:
                if not client.bucket_exists(bucket):
                    client.make_bucket(bucket)
                print(f"ok {bucket}")
            return
        except Exception:
            if attempt == 29:
                raise
            time.sleep(1)


if __name__ == "__main__":
    main()
