from photochart.organizer.adapters import build_adapter
from photochart.organizer.adapters.pcloud_api import PCloudApiAdapter
from photochart.organizer.adapters.webdav import NextcloudAdapter
from photochart.organizer.config import OrganizerConfig


class FakePCloud(PCloudApiAdapter):
    def __init__(self) -> None:
        super().__init__("secret")

    def _call(self, method: str, **parameters):
        assert method == "listfolder"
        return {
            "metadata": {
                "contents": [
                    {
                        "name": "nested",
                        "isfolder": True,
                        "contents": [
                            {
                                "name": "photo.jpg",
                                "fileid": 42,
                                "size": 123,
                                "modified": "Mon, 28 Sep 2026 10:00:00 +0000",
                            }
                        ],
                    }
                ]
            }
        }


def test_pcloud_recursive_listing() -> None:
    objects = list(FakePCloud().list_objects("/PhotoUpload"))

    assert len(objects) == 1
    assert objects[0].path == "/PhotoUpload/nested/photo.jpg"
    assert objects[0].object_id == "42"


def test_factory_reads_secret_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("PCLOUD_TEST_TOKEN", "token")
    config = OrganizerConfig(
        "/in",
        "/out",
        adapter="pcloud_api",
        adapter_options={"access_token_env": "PCLOUD_TEST_TOKEN"},
    )

    adapter = build_adapter(config)

    assert isinstance(adapter, PCloudApiAdapter)
    assert adapter.access_token == "token"


def test_nextcloud_builds_dav_endpoint() -> None:
    adapter = NextcloudAdapter("https://cloud.example", "user", "password")

    assert adapter.endpoint.endswith("/remote.php/dav/files/user")
