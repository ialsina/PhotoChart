"""Direct pCloud REST API adapter."""

from __future__ import annotations

import io
import json
import posixpath
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, BinaryIO, Iterator, Mapping

from ..domain import MediaObject, StorageCapabilities


class PCloudApiAdapter:
    adapter_id = "pcloud_api"

    def __init__(
        self,
        access_token: str,
        *,
        endpoint: str = "https://api.pcloud.com",
        timeout: float = 60,
    ) -> None:
        self.access_token = access_token
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout

    def _call(self, method: str, **parameters: Any) -> Mapping[str, Any]:
        query = urllib.parse.urlencode(
            {"access_token": self.access_token, **parameters}
        )
        with urllib.request.urlopen(
            f"{self.endpoint}/{method}?{query}", timeout=self.timeout
        ) as response:
            payload = json.load(response)
        if payload.get("result", 0) != 0:
            raise OSError(
                f"pCloud API error {payload.get('result')}: {payload.get('error')}"
            )
        return payload

    @staticmethod
    def _modified(value: Any) -> datetime | None:
        if not value:
            return None
        parsed = datetime.strptime(str(value), "%a, %d %b %Y %H:%M:%S %z")
        return parsed.astimezone(timezone.utc)

    def _media(self, item: Mapping[str, Any]) -> MediaObject:
        path = str(item.get("path") or item.get("name"))
        return MediaObject(
            self.adapter_id,
            str(item.get("fileid") or item.get("id") or path),
            path,
            str(item.get("name") or posixpath.basename(path)),
            int(item.get("size", 0)),
            self._modified(item.get("modified")),
            item.get("contenttype"),
            item,
        )

    def list_objects(self, path: str) -> Iterator[MediaObject]:
        payload = self._call("listfolder", path=path, recursive=1, showdeleted=0)

        def walk(item: Mapping[str, Any], parent: str) -> Iterator[MediaObject]:
            for child in item.get("contents", []):
                child_path = posixpath.join(parent, str(child.get("name", "")))
                child = dict(child)
                child["path"] = child_path
                if child.get("isfolder"):
                    yield from walk(child, child_path)
                elif not child.get("isdeleted"):
                    yield self._media(child)

        metadata = payload.get("metadata", {})
        yield from walk(metadata, path.rstrip("/"))

    def get_object_info(self, path: str) -> MediaObject:
        return self._media(self._call("stat", path=path)["metadata"])

    @contextmanager
    def open_read(self, path: str) -> Iterator[BinaryIO]:
        payload = self._call("getfilelink", path=path, forcedownload=1)
        hosts = payload.get("hosts") or []
        if not hosts:
            raise OSError("pCloud did not return a download host")
        url = f"https://{hosts[0]}{payload['path']}"
        with urllib.request.urlopen(url, timeout=self.timeout) as response:
            yield response

    def ensure_directory(self, path: str) -> None:
        self._call("createfolderifnotexists", path=path)

    def copy(self, source: str, destination: str) -> None:
        self._call(
            "copyfile",
            path=source,
            topath=destination,
            noover=1,
        )

    def move(self, source: str, destination: str) -> None:
        self._call("renamefile", path=source, topath=destination, noover=1)

    def delete(self, path: str) -> None:
        self._call("deletefile", path=path)

    def exists(self, path: str) -> bool:
        try:
            self._call("stat", path=path)
            return True
        except OSError as error:
            if "2009" in str(error):
                return False
            raise

    def get_capabilities(self) -> StorageCapabilities:
        return StorageCapabilities(
            server_side_move=True,
            streaming_read=True,
            random_read=False,
        )

    def healthcheck(self) -> None:
        self._call("userinfo")
