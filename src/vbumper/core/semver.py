import re
from dataclasses import dataclass, replace
from functools import total_ordering

_SEMVER_RE = re.compile(
    r"""
    ^
    (0|[1-9]\d*)\.
    (0|[1-9]\d*)\.
    (0|[1-9]\d*)
    (?:-((?:0|[1-9]\d*|[A-Za-z-][0-9A-Za-z-]*)
        (?:\.(?:0|[1-9]\d*|[A-Za-z-][0-9A-Za-z-]*))*))?
    (?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?
    $
    """,
    re.VERBOSE,
)


def bump_trailing_number(value: str) -> str:
    match = re.search(r"(?:^|\.)(0|[1-9]\d*)$", value)

    if not match:
        return f"{value}.1"

    start, end = match.span(1)
    number = int(match.group(1)) + 1

    return f"{value[:start]}{number}{value[end:]}"


@total_ordering
@dataclass(frozen=True, slots=True)
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: str | None = None
    build: str | None = None

    def __post_init__(self) -> None:
        for name in ("major", "minor", "patch"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")

        version = str(self)
        if not _SEMVER_RE.fullmatch(version):
            raise ValueError(f"invalid semantic version: {version!r}")

    @classmethod
    def parse(cls, value: str) -> SemVer:
        match = _SEMVER_RE.fullmatch(value)
        if not match:
            raise ValueError(f"invalid semantic version: {value!r}")

        major, minor, patch, prerelease, build = match.groups()

        return cls(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=prerelease,
            build=build,
        )

    def copy(
        self,
        *,
        major: int | None = None,
        minor: int | None = None,
        patch: int | None = None,
        prerelease: str | None = None,
        build: str | None = None,
        clear_prerelease: bool = False,
        clear_build: bool = False,
    ) -> SemVer:
        return replace(
            self,
            major=self.major if major is None else major,
            minor=self.minor if minor is None else minor,
            patch=self.patch if patch is None else patch,
            prerelease=None
            if clear_prerelease
            else (self.prerelease if prerelease is None else prerelease),
            build=None if clear_build else (self.build if build is None else build),
        )

    def bump_major(self) -> SemVer:
        return SemVer(self.major + 1, 0, 0)

    def bump_minor(self) -> SemVer:
        return SemVer(self.major, self.minor + 1, 0)

    def bump_patch(self) -> SemVer:
        return SemVer(self.major, self.minor, self.patch + 1)

    def bump_prerelease(self) -> SemVer:
        if self.prerelease is None:
            raise ValueError("prerelease is None")

        return self.copy(
            prerelease=bump_trailing_number(self.prerelease),
            clear_build=True,
        )

    def with_advanced_prerelease(self, token: str | None = None) -> SemVer:
        """Move into, or advance within, a prerelease sequence -- the shared logic behind the
        CLI's `prerelease`/`rc`/`alpha`/`beta` commands.

        If this version is not already a prerelease, starts one at `"<token or 'rc'>.1"`. If it
        is already a prerelease and `token` is `None` or names the same leading token, the
        trailing numeric serial is incremented (or appended as `.1` if the prerelease has none).
        If `token` names a *different* leading token, the prerelease is replaced with
        `"<token>.1"` instead. Always clears build metadata, like `bump_prerelease`."""

        if self.prerelease is None:
            return self.copy(prerelease=f"{token or 'rc'}.1", clear_build=True)

        match = re.fullmatch(r"(.+)\.(\d+)", self.prerelease)
        if match:
            current_token, current_serial = match.group(1), int(match.group(2))
        else:
            current_token, current_serial = self.prerelease, 0

        if token is None or token == current_token:
            new_token, new_serial = current_token, current_serial + 1
        else:
            new_token, new_serial = token, 1

        return self.copy(prerelease=f"{new_token}.{new_serial}", clear_build=True)

    def with_prerelease(self, prerelease: str) -> SemVer:
        return self.copy(prerelease=prerelease, clear_build=True)

    def without_prerelease(self) -> SemVer:
        return self.copy(clear_prerelease=True)

    def with_build(self, build: str) -> SemVer:
        return self.copy(build=build)

    def without_build(self) -> SemVer:
        return self.copy(clear_build=True)

    def is_identical_to(self, other: object) -> bool:
        return isinstance(other, SemVer) and (
            self.major,
            self.minor,
            self.patch,
            self.prerelease,
            self.build,
        ) == (
            other.major,
            other.minor,
            other.patch,
            other.prerelease,
            other.build,
        )

    def __str__(self) -> str:
        result = f"{self.major}.{self.minor}.{self.patch}"

        if self.prerelease is not None:
            result += f"-{self.prerelease}"

        if self.build is not None:
            result += f"+{self.build}"

        return result

    def __repr__(self) -> str:
        return f"{type(self).__name__}.parse({str(self)!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented

        return self._precedence_key() == other._precedence_key()

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented

        core_cmp = self._core_key() < other._core_key()
        if self._core_key() != other._core_key():
            return core_cmp

        return self._compare_prerelease(other) < 0

    def __hash__(self) -> int:
        # Matches __eq__: build metadata is ignored.
        return hash(self._precedence_key())

    def _core_key(self) -> tuple[int, int, int]:
        return self.major, self.minor, self.patch

    def _precedence_key(self) -> tuple[int, int, int, str | None]:
        # Build metadata intentionally ignored.
        return self.major, self.minor, self.patch, self.prerelease

    def _compare_prerelease(self, other: SemVer) -> int:
        left = self.prerelease
        right = other.prerelease

        if left is None and right is None:
            return 0

        if left is None:
            return 1

        if right is None:
            return -1

        left_parts = left.split(".")
        right_parts = right.split(".")

        for left_part, right_part in zip(left_parts, right_parts):
            cmp = _compare_prerelease_identifier(left_part, right_part)
            if cmp != 0:
                return cmp

        return (len(left_parts) > len(right_parts)) - (len(left_parts) < len(right_parts))


def _compare_prerelease_identifier(left: str, right: str) -> int:
    left_is_num = left.isdigit()
    right_is_num = right.isdigit()

    if left_is_num and right_is_num:
        left_num = int(left)
        right_num = int(right)
        return (left_num > right_num) - (left_num < right_num)

    if left_is_num:
        return -1

    if right_is_num:
        return 1

    return (left > right) - (left < right)


__all__ = ["SemVer", "bump_trailing_number"]
