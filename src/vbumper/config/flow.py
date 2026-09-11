import re
from typing import Annotated

import pydantic

#: Key under which a flow is registered under a project's `flows:` or a `~/.vbumpconfig.yaml`'s
#: `flows:`, and the value accepted by `--flow=NAME`. Lowercase letters, digits, and hyphens,
#: starting with a letter (kept in sync with the `flowKey` definition in
#: `vbumper-config.schema.json`).
FLOW_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")

#: See `FLOW_KEY_PATTERN`.
FlowKey = Annotated[str, pydantic.StringConstraints(pattern=FLOW_KEY_PATTERN.pattern)]

#: A single command, run through the operating system's own command shell after placeholder
#: substitution (`/bin/sh` on Unix-like systems, `cmd.exe` on Windows). May contain the
#: placeholders `{VERSION}`, `{VERSION_TAG}`, and any name declared under a flow's own
#: `variables:`, substituted at execution time (substitution itself is not this model's concern).
#: `stage_command` additionally accepts `{CHANGED_FILE}`, meaningless anywhere else (see
#: `FlowDefinition.stage_command`). Substitution is verbatim: no value is quoted or escaped on the
#: flow's behalf, so a command that relies on a substituted value being treated as a single shell
#: word is responsible for its own quoting.
Command = Annotated[str, pydantic.Field(min_length=1)]

#: Placeholder names reserved for vbumper's own substitutions: a flow's `variables:` may not
#: redefine these.
RESERVED_VARIABLE_NAMES = frozenset({"VERSION", "VERSION_TAG", "CHANGED_FILE"})

#: Key accepted in a flow's `variables:` mapping: an uppercase placeholder-style identifier, kept
#: in sync with the `flowVariableName` definition in `vbumper-config.schema.json`.
VARIABLE_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
VariableName = Annotated[str, pydantic.StringConstraints(pattern=VARIABLE_NAME_PATTERN.pattern)]


class FlowDefinition(pydantic.BaseModel):
    """A named Git release workflow: a sequence of pre-write-back commands, the version-file
    write-back itself (not represented here: it always happens between the two command lists),
    an optional per-file staging command, and a sequence of post-write-back commands.

    No flow, built-in or user-defined, receives any special treatment from vbumper: every
    global option, precondition, and config value applies identically regardless of which flow
    (if any) is selected. `variables` is the generic, flow-agnostic bag of per-flow *data* fed
    into command substitution; `require_on_branch` is a separate, purely precondition-only check.
    The engine code that enforces/substitutes them is the same for every flow.

    This is the shape a flow's *definition* takes, whether written directly under a project's own
    `flows:` or under `~/.vbumpconfig.yaml`'s `flows:`. The two files play different roles:
    a project's own `flows:` is what `bump` actually resolves against; `~/.vbumpconfig.yaml`'s
    `flows:` is a template library, only ever read by `vbump flow add`/`vbump init --flows` to
    copy a flow into a project's own config, but the shape of one flow's definition is identical
    either way, and neither can refer to the other at runtime.
    """

    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    name: str | None = None
    require_on_branch: str | None = None
    variables: dict[VariableName, str] = pydantic.Field(default_factory=dict)
    pre_commands: list[Command] = pydantic.Field(default_factory=list)
    stage_command: Command | None = None
    post_commands: list[Command] = pydantic.Field(default_factory=list)

    @pydantic.field_validator("variables")
    @classmethod
    def _forbid_reserved_variable_names(cls, value: dict[str, str]) -> dict[str, str]:
        reserved_used = RESERVED_VARIABLE_NAMES & value.keys()
        if reserved_used:
            raise ValueError(
                f"variables: may not redefine reserved placeholder(s):"
                f" {', '.join(sorted(reserved_used))}"
            )
        return value


__all__ = [
    "FLOW_KEY_PATTERN",
    "RESERVED_VARIABLE_NAMES",
    "VARIABLE_NAME_PATTERN",
    "Command",
    "FlowDefinition",
    "FlowKey",
    "VariableName",
]
