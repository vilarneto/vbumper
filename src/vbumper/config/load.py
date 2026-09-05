from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .root import VBumpConfig

#: Candidate file names, checked in this order.
_CONFIG_FILE_NAMES = (".vbump.yaml", ".vbump.yml")


def find_config_path(start: str | Path = ".") -> Path | None:
    """Return the `.vbump.yaml`/`.vbump.yml` in `start`, or `None`.

    `start` must name a directory -- it is the discovery root, and no directory above it is ever
    consulted. A project with `--dir`/`-d` pointing below its actual config file is not expected
    to pick that config up; it is expected to be run from (or point at) the root that owns it.

    A directory that genuinely has no config file in it is fine -- that's just "no config file
    here". A directory that could not be *checked* (e.g. permission denied) is not: that is
    surfaced as an exception rather than silently treated as "no config file here", since the two
    cases are easy to confuse and only one of them is safe to ignore.
    """

    from vbumper.core.exceptions import ConfigurationError

    search_dir = Path(start)
    if not search_dir.is_dir():
        raise ConfigurationError(f"{search_dir} is not a directory -- --dir/-d requires one")

    for file_name in _CONFIG_FILE_NAMES:
        candidate = search_dir / file_name
        try:
            is_file = candidate.is_file()
        except OSError as exc:
            raise OSError(f"Could not check for a config file at {candidate}: {exc}") from exc

        if is_file:
            return candidate

    return None


def raise_configuration_error(path: Path, cause: Exception) -> None:
    import pydantic
    from ruamel.yaml import YAMLError

    from vbumper.core.exceptions import ConfigurationError

    if isinstance(cause, YAMLError):
        location = ""
        mark = getattr(cause, "problem_mark", None)
        if mark is not None:
            location = f":{mark.line + 1}:{mark.column + 1}"
        raise ConfigurationError(f"{path}{location}: {cause}") from cause

    if isinstance(cause, pydantic.ValidationError):
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or '<root>'}: {error['msg']}"
            for error in cause.errors()
        )
        raise ConfigurationError(f"{path}: {details}") from cause

    raise ConfigurationError(f"{path}: {cause}") from cause


def load_config_file(path: str | Path) -> VBumpConfig:
    """Parse and validate a single config file. Raises `ConfigurationError` on failure.

    Only the current config shape (`version: 3`) is accepted -- an older schema version is
    refused outright, via `VBumpConfig`'s own version validator.
    """

    import pydantic
    from ruamel.yaml import YAML, YAMLError

    from .root import VBumpConfig

    path = Path(path)

    yaml = YAML(typ="safe")
    with path.open("rt", encoding="utf-8") as fd:
        try:
            raw = yaml.load(fd)
        except YAMLError as exc:
            raise_configuration_error(path, exc)
            raise  # pragma: no cover -- raise_configuration_error always raises

    raw = raw if raw is not None else {}

    try:
        return VBumpConfig.model_validate(raw)
    except pydantic.ValidationError as exc:
        raise_configuration_error(path, exc)
        raise  # pragma: no cover -- raise_configuration_error always raises


def load_config(start: str | Path = ".") -> VBumpConfig:
    """Load the `.vbump.yaml`/`.vbump.yml` in `start` (see `find_config_path`).

    Unlike a project's own `discoverers:` entries, the config file itself is mandatory -- every
    discoverer, built-in types included, is opt-in (see
    `vbumper.core.resolution.discover_containers`), so a missing config file would otherwise
    silently discover nothing project-wide with no indication why. `vbump init` scaffolds a
    starting file, auto-populated with a `- type: ...` entry for each built-in that matches
    something already present in the target directory."""

    from vbumper.core.exceptions import ConfigurationError

    search_dir = Path(start)
    config_path = find_config_path(start)
    if config_path is None:
        raise ConfigurationError(
            f"No .vbump.yaml/.vbump.yml found in {search_dir} -- run 'vbump init' to create one"
        )

    return load_config_file(config_path)


__all__ = [
    "find_config_path",
    "load_config",
    "load_config_file",
    "raise_configuration_error",
]
