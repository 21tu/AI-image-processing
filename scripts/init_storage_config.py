"""Generate the local object store identity without embedding secrets in the image."""

import json
import os
from pathlib import Path


def main() -> None:
    config = {
        "identities": [
            {
                "name": "visionguard-local",
                "credentials": [
                    {
                        "accessKey": os.environ["S3_ACCESS_KEY"],
                        "secretKey": os.environ["S3_SECRET_KEY"],
                    }
                ],
                "actions": ["Admin", "Read", "Write", "List", "Tagging"],
            }
        ]
    }
    path = Path("/config/seaweedfs-s3.json")
    path.write_text(json.dumps(config), encoding="utf-8")
    path.chmod(0o600)


if __name__ == "__main__":
    main()
