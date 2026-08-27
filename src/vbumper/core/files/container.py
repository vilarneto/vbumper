import pathlib
import shlex
from typing import Any

from vbumper.core.semver import SemVer

from ..containers.base import VersionContainer
from ..containers.types import NO_SEMVER, NoSemVer, Versioned, resolve_status


def describe_file_container(file_path: pathlib.Path) -> str:
    return f"File {shlex.quote(str(file_path))}"


class TextFileContentsVersionContainer(VersionContainer):
    _encoding: str
    _file_path: pathlib.Path
    _chunks: list[bytes]

    def __init__(
        self,
        *,
        file_path: pathlib.Path,
        version_chunks: list[bytes],
        chunks: list[bytes],
        encoding: str = "utf-8",
    ):
        if len(chunks) < 2:
            raise ValueError(
                "Text chunks must contain at least two parts: before and after version"
            )
        if len(version_chunks) != len(chunks) - 1:
            raise ValueError("Expected exactly one version chunk between each pair of chunks")

        self._encoding = encoding
        self._file_path = file_path
        self._chunks = chunks

        copies = [
            self._parse_copy(self._decode_from_file(version_chunk))
            for version_chunk in version_chunks
        ]

        super().__init__(status=resolve_status(copies))

    # noinspection PyMethodMayBeStatic
    def _decode_from_file(self, file_chunk: bytes) -> str:
        return file_chunk.decode(self._encoding)

    # noinspection PyMethodMayBeStatic
    def _parse_copy(self, raw: str) -> SemVer | NoSemVer | None:
        """Parse one copy's raw captured string: an empty string is an unversioned copy
        (`NO_SEMVER`), an unparseable non-empty string is `None` (its raw content is not
        retained), otherwise the parsed `SemVer`."""
        if raw == "":
            return NO_SEMVER

        try:
            return SemVer.parse(raw)
        except ValueError:
            return None

    def describe(self) -> str:
        return describe_file_container(self._file_path)

    def write(self) -> None:
        if not isinstance(self.status, Versioned):
            raise ValueError(
                "Cannot write a version container whose status is not a resolved version"
            )

        encoded_version = str(self.status.value).encode(self._encoding)

        with self._file_path.open("wb") as fd:
            for index in range(len(self._chunks) - 1):
                fd.write(self._chunks[index])
                fd.write(encoded_version)

            fd.write(self._chunks[-1])


class JSONFileVersionContainer(VersionContainer):
    """A version container backed by a single string value at a top-level key of a JSON file
    (e.g. `package.json`'s `"version"`), rewritten as a whole file on write-back rather than by
    patching a byte range -- there is no stable "surrounding text" to preserve the way there is
    for `TextFileContentsVersionContainer`'s regex-matched containers.

    A missing key, or a key whose value isn't a string at all, is not a version container --
    callers (the discoverer) should never construct one for that case; the boundary between
    "not a version container" and "unversioned" is a per-container-type judgment call."""

    _encoding: str
    _file_path: pathlib.Path
    _data: dict[str, Any]
    _version_key: str

    def __init__(
        self,
        *,
        file_path: pathlib.Path,
        data: dict[str, Any],
        version_key: str = "version",
        encoding: str = "utf-8",
    ):
        self._encoding = encoding
        self._file_path = file_path
        self._data = data
        self._version_key = version_key

        super().__init__(status=resolve_status([self._parse_copy(data[version_key])]))

    # noinspection PyMethodMayBeStatic
    def _parse_copy(self, raw: str) -> SemVer | NoSemVer | None:
        """See `TextFileContentsVersionContainer._parse_copy` for the same convention: empty
        string is unversioned (`NO_SEMVER`), unparseable non-empty is `None` (raw content
        discarded), otherwise the parsed `SemVer`."""
        if raw == "":
            return NO_SEMVER

        try:
            return SemVer.parse(raw)
        except ValueError:
            return None

    def describe(self) -> str:
        return describe_file_container(self._file_path)

    def write(self) -> None:
        import json

        if not isinstance(self.status, Versioned):
            raise ValueError(
                "Cannot write a version container whose status is not a resolved version"
            )

        data = dict(self._data)
        data[self._version_key] = str(self.status.value)

        with self._file_path.open("wt", encoding=self._encoding) as fd:
            json.dump(data, fd, ensure_ascii=False, indent=2)
            fd.write("\n")


__all__ = [
    "JSONFileVersionContainer",
    "TextFileContentsVersionContainer",
    "describe_file_container",
]
