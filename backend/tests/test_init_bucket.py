from contextlib import closing

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber
from scripts.init_bucket import ensure_bucket


@pytest.fixture
def s3():
    with closing(
        boto3.client(
            "s3",
            endpoint_url="http://localhost:9000",
            aws_access_key_id="test",
            aws_secret_access_key="test",
            region_name="us-east-1",
        )
    ) as client:
        yield client


def test_existing_bucket_is_not_recreated(s3):
    with Stubber(s3) as stub:
        stub.add_response("head_bucket", {}, {"Bucket": "visionguard"})
        ensure_bucket(s3, "visionguard", "us-east-1")
        stub.assert_no_pending_responses()


@pytest.mark.parametrize("region", ["us-east-1", "eu-west-1"])
def test_missing_bucket_is_created_and_checked(s3, region):
    with Stubber(s3) as stub:
        stub.add_client_error(
            "head_bucket",
            "404",
            http_status_code=404,
            expected_params={"Bucket": "visionguard"},
        )
        options = {"Bucket": "visionguard"}
        if region != "us-east-1":
            options["CreateBucketConfiguration"] = {"LocationConstraint": region}
        stub.add_response("create_bucket", {}, options)
        stub.add_response("head_bucket", {}, {"Bucket": "visionguard"})
        ensure_bucket(s3, "visionguard", region)
        stub.assert_no_pending_responses()


def test_access_denied_does_not_trigger_bucket_creation(s3):
    with Stubber(s3) as stub:
        stub.add_client_error("head_bucket", "403", http_status_code=403)
        with pytest.raises(ClientError):
            ensure_bucket(s3, "visionguard", "us-east-1")
        stub.assert_no_pending_responses()


def test_storage_readiness_uses_and_closes_s3_client(s3, monkeypatch):
    from visionguard.api.routes import health

    monkeypatch.setattr(health.boto3, "client", lambda *args, **kwargs: s3)
    with Stubber(s3) as stub:
        stub.add_response(
            "head_bucket", {}, {"Bucket": health.get_settings().s3_bucket}
        )
        health.check_storage()
        stub.assert_no_pending_responses()


def test_startup_retries_are_bounded(s3, monkeypatch, capsys):
    from scripts import init_bucket

    monkeypatch.setattr(init_bucket.boto3, "client", lambda *args, **kwargs: s3)
    sleeps = []
    monkeypatch.setattr(init_bucket.time, "sleep", sleeps.append)
    with Stubber(s3) as stub:
        for _ in range(30):
            stub.add_client_error("head_bucket", "503", http_status_code=503)
        assert init_bucket.main() == 1
        stub.assert_no_pending_responses()
    assert sleeps == [2] * 29
    assert "attempt 30/30 failed" in capsys.readouterr().out
