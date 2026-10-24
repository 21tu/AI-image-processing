"""Upload smoke check; generates PNG bytes using only the standard library."""

import argparse
import json
import struct
import urllib.error
import urllib.request
import zlib


def png():
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + chunk(b"IEND", b"")
    )


def upload(base, data):
    boundary = "visionguard-smoke-boundary"
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="test.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
        ).encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request = urllib.request.Request(
        base + "/api/v1/media",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    status, asset = upload(args.base_url, png())
    print(f"POST valid: {status}")
    assert status == 201, asset
    with urllib.request.urlopen(
        args.base_url + "/api/v1/media/" + asset["id"], timeout=10
    ) as response:
        assert response.status == 200
        assert json.load(response) == asset
        print("GET metadata: 200")
    status, _ = upload(args.base_url, b"text renamed as png")
    print(f"POST spoofed: {status}")
    assert status in (415, 422)


if __name__ == "__main__":
    main()
