class VBumpError(Exception):
    pass


class ConfigurationError(VBumpError):
    pass


class ReadOnlyVersionContainerError(VBumpError):
    pass


class IncompatibleVersionsError(VBumpError):
    pass


class NoBaseVersionError(VBumpError):
    """Raised when a bump command needs an existing version to compute from, but no discovered
    container is `Versioned` (e.g. every container is `Unversioned`, or none was discovered at
    all). `set` never raises this, since an explicit target needs no prior version."""


class DiscovererFailure(VBumpError):
    container_description: str

    def __init__(self, *args, container_description: str):
        super().__init__(*args)
        self.container_description = container_description


class UnknownFlowError(VBumpError):
    """Raised when `--flow NAME` names a flow not declared under the config's `flows:`."""


class DirtyRepositoryError(VBumpError):
    """Raised when a flow is selected but the working tree is dirty and
    `--allow-dirty-repository` was not passed."""


class WrongBranchError(VBumpError):
    """Raised when a flow's `develop_branch` doesn't match the repository's current branch."""


class FlowCommandFailure(VBumpError):
    """Raised when a flow's `pre_commands`/`post_commands` entry (or an internal `git` read used
    to check preconditions) exits non-zero, or when running it fails outright.

    No rollback is attempted for commands that already ran -- this mirrors write-back's own
    no-rollback stance (see `WriteBackFailure`) for the flow engine."""

    def __init__(self, *args, command: list[str], returncode: int):
        super().__init__(*args)
        self.command = command
        self.returncode = returncode


class WriteBackFailure(VBumpError):
    """Raised when write-back aborts partway through because one container's `write()` failed.

    Carries which containers were already written and which were never reached, so the caller
    can report a precise, actionable summary -- write-back never rolls back what already
    succeeded, aborting immediately at the first failure instead."""

    def __init__(
        self,
        *args,
        failed_description: str,
        written_descriptions: list[str],
        not_reached_descriptions: list[str],
    ):
        super().__init__(*args)
        self.failed_description = failed_description
        self.written_descriptions = written_descriptions
        self.not_reached_descriptions = not_reached_descriptions


__all__ = [
    "ConfigurationError",
    "DirtyRepositoryError",
    "DiscovererFailure",
    "FlowCommandFailure",
    "IncompatibleVersionsError",
    "NoBaseVersionError",
    "ReadOnlyVersionContainerError",
    "UnknownFlowError",
    "VBumpError",
    "WriteBackFailure",
    "WrongBranchError",
]
