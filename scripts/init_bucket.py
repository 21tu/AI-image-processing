"""Create the configured S3 bucket, with bounded startup retries."""

import time
from contextlib import closing

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from visionguard.core.config import get_settings


def ensure_bucket(client, bucket: str, region: str) -> None:
    try:
        client.head_bucket(Bucket=bucket)
        return
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in {"404", "NoSuchBucket", "NotFound"}:
            raise
    options = {"Bucket": bucket}
    if region != "us-east-1":
        options["CreateBucketConfiguration"] = {"LocationConstraint": region}
    try:
        client.create_bucket(**options)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "BucketAlreadyOwnedByYou":
            raise
    client.head_bucket(Bucket=bucket)


def main() -> int:
    settings = get_settings()
    with closing(
        boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key.get_secret_value(),
            aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
            region_name=settings.s3_region,
            config=Config(
                connect_timeout=2,
                read_timeout=2,
                retries={"total_max_attempts": 1},
                s3={"addressing_style": "path"},
            ),
        )
    ) as client:
        for attempt in range(30):
            try:
                ensure_bucket(client, settings.s3_bucket, settings.s3_region)
                print("S3 bucket is ready")
                return 0
            except BotoCoreError, ClientError:
                # Avoid leaking credentials or endpoint details in startup logs.
                print(f"S3 bucket initialization attempt {attempt + 1}/30 failed")
                if attempt < 29:
                    time.sleep(2)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
