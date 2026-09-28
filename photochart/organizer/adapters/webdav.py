"""WebDAV and Nextcloud storage adapters."""

from __future__ import annotations

import base64
import email.utils
import io
import posixpath
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ElementTree
from contextlib import contextmanager
from datetime import timezone
from typing import BinaryIO, Iterator

from ..domain import MediaObject, StorageCapabilities

DAV = "{DAV:}"


class WebDavAdapter:
    adapter_id = "webdav"

    def __init__(
        self,
        endpoint: str,
        username: str,
        password: str,
        *,
        timeout: float = 60,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._authorization = f"Basic {token}"

    def _url(self, path: str) -> str:
        quoted = urllib.parse.quote("/" + path.lstrip("/"), safe="/")
        return self.endpoint + quoted

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ):
        request_headers = {"Authorization": self._authorization}
        request_headers.update(headers or {})
        request = urllib.request.Request(
            self._url(path), data=data, headers=request_headers, method=method
        )
        return urllib.request.urlopen(request, timeout=self.timeout)

    def list_objects(self, path: str) -> Iterator[MediaObject]:
        directories = [path]
        while directories:
            directory = directories.pop()
            with self._request(
                "PROPFIND", directory, headers={"Depth": "1"}
            ) as response:
                root = ElementTree.fromstring(response.read())
            base_url = self._url(directory).rstrip("/")
            for item in root.findall(f"{DAV}response"):
                href = item.findtext(f"{DAV}href", "")
                item_url = urllib.parse.urljoin(self.endpoint + "/", href).rstrip("/")
                if item_url == base_url:
                    continue
                prop = item.find(f".//{DAV}prop")
                if prop is None:
                    continue
                resource_type = prop.find(f"{DAV}resourcetype")
                decoded_path = urllib.parse.unquote(
                    urllib.parse.urlparse(item_url).path
                )
                endpoint_path = urllib.parse.urlparse(self.endpoint).path.rstrip("/")
                relative_path = decoded_path[len(endpoint_path) :] or "/"
                if (
                    resource_type is not None
                    and resource_type.find(f"{DAV}collection") is not None
                ):
                    directories.append(relative_path)
                    continue
                size = int(prop.findtext(f"{DAV}getcontentlength", "0"))
                modified = email.utils.parsedate_to_datetime(
                    prop.findtext(f"{DAV}getlastmodified")
                )
                if modified.tzinfo is None:
                    modified = modified.replace(tzinfo=timezone.utc)
                yield MediaObject(
                    self.adapter_id,
                    href,
                    relative_path,
                    posixpath.basename(relative_path),
                    size,
                    modified,
                    prop.findtext(f"{DAV}getcontenttype"),
                )

    def get_object_info(self, path: str) -> MediaObject:
        parent = posixpath.dirname(path) or "/"
        for item in self.list_objects(parent):
            if item.path.rstrip("/") == path.rstrip("/"):
                return item
        raise FileNotFoundError(path)

    @contextmanager
    def open_read(self, path: str) -> Iterator[BinaryIO]:
        with self._request("GET", path) as response:
            yield response

    def ensure_directory(self, path: str) -> None:
        current = ""
        for part in path.strip("/").split("/"):
            current += "/" + part
            try:
                self._request("MKCOL", current).close()
            except urllib.error.HTTPError as error:
                if error.code not in (405, 409):
                    raise

    def copy(self, source: str, destination: str) -> None:
        self._request(
            "COPY",
            source,
            headers={"Destination": self._url(destination), "Overwrite": "F"},
        ).close()

    def move(self, source: str, destination: str) -> None:
        self._request(
            "MOVE",
            source,
            headers={"Destination": self._url(destination), "Overwrite": "F"},
        ).close()

    def delete(self, path: str) -> None:
        self._request("DELETE", path).close()

    def exists(self, path: str) -> bool:
        try:
            self._request("HEAD", path).close()
            return True
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return False
            raise

    def get_capabilities(self) -> StorageCapabilities:
        return StorageCapabilities(
            server_side_move=True,
            random_read=True,
            streaming_read=True,
            resumable_transfer=False,
        )

    def healthcheck(self) -> None:
        self._request("PROPFIND", "/", headers={"Depth": "0"}).close()


class NextcloudAdapter(WebDavAdapter):
    adapter_id = "nextcloud"

    def __init__(
        self,
        endpoint: str,
        username: str,
        password: str,
        *,
        timeout: float = 60,
    ) -> None:
        webdav_endpoint = (
            endpoint.rstrip("/")
            + f"/remote.php/dav/files/{urllib.parse.quote(username)}"
        )
        super().__init__(webdav_endpoint, username, password, timeout=timeout)
