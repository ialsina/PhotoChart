from datetime import datetime, timezone
from io import BytesIO

from photochart.organizer.adapters.s3 import S3Adapter


class Paginator:
    def __init__(self, client) -> None:
        self.client = client

    def paginate(self, Bucket, Prefix):
        yield {
            "Contents": [
                {
                    "Key": key,
                    "Size": len(value),
                    "ETag": key,
                    "LastModified": datetime(2026, 9, 28, tzinfo=timezone.utc),
                }
                for key, value in self.client.objects.items()
                if key.startswith(Prefix)
            ]
        }


class FakeS3:
    def __init__(self) -> None:
        self.objects = {"PhotoUpload/photo.jpg": b"photo"}

    def get_paginator(self, name):
        return Paginator(self)

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            error = RuntimeError("missing")
            error.response = {"Error": {"Code": "404"}}
            raise error
        return {
            "ContentLength": len(self.objects[Key]),
            "ETag": Key,
            "LastModified": datetime(2026, 9, 28, tzinfo=timezone.utc),
        }

    def get_object(self, Bucket, Key):
        return {"Body": BytesIO(self.objects[Key])}

    def copy(self, source, bucket, key):
        self.objects[key] = self.objects[source["Key"]]

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)

    def head_bucket(self, Bucket):
        return {}


def test_s3_lists_and_moves_with_verification() -> None:
    client = FakeS3()
    adapter = S3Adapter("photos", client=client)

    objects = list(adapter.list_objects("/PhotoUpload"))
    adapter.move("/PhotoUpload/photo.jpg", "/Photos/2026/photo.jpg")

    assert objects[0].name == "photo.jpg"
    assert "PhotoUpload/photo.jpg" not in client.objects
    assert client.objects["Photos/2026/photo.jpg"] == b"photo"
    assert adapter.get_capabilities().object_storage


def test_s3_not_found_is_distinct() -> None:
    adapter = S3Adapter("photos", client=FakeS3())

    assert not adapter.exists("/missing.jpg")
