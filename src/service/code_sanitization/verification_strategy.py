"""Strategy-based discovery of build/test verification commands.

Strategies are selected from repository configuration plus the language inferred
from the changed files, so verification is not hardcoded into the gate tool.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Iterable, Mapping

UNKNOWN_PROJECT_TYPE = "unknown"
AUTO_PROJECT_TYPE = "auto"
NONE_PROJECT_TYPE = "none"


@dataclass(frozen=True)
class VerificationContext:
    """Inputs available when choosing verification commands."""

    repo_path: Path
    junit_xml_path: Path
    coverage_xml_path: Path
    changed_files: tuple[str, ...] = ()
    language: str | None = None


@dataclass(frozen=True)
class VerificationCommands:
    """Build and test commands resolved for a repository."""

    project_type: str = UNKNOWN_PROJECT_TYPE
    build_command: list[str] | None = None
    test_command: list[str] | None = None
    pre_build_commands: list[list[str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_type": self.project_type,
            "build_command": self.build_command,
            "test_command": self.test_command,
            "pre_build_commands": self.pre_build_commands,
        }


class VerificationCommandStrategy(ABC):
    """Resolve build/test commands for one project ecosystem."""

    project_type: ClassVar[str] = UNKNOWN_PROJECT_TYPE
    languages: ClassVar[frozenset[str]] = frozenset()

    @abstractmethod
    def matches(self, context: VerificationContext) -> bool:
        """Whether this strategy recognizes the repository layout."""

    @abstractmethod
    def build(self, context: VerificationContext) -> VerificationCommands:
        """Build the commands for the repository."""


@dataclass
class VerificationCommandOverride:
    """Explicit command overrides for one language.

    ``build_command``/``test_command`` replace the discovered command entirely,
    while ``extra_build_args``/``extra_test_args`` are appended to it, so
    repository-specific flags can be added without losing auto-discovery of the
    solution or test project.
    """

    build_command: list[str] | None = None
    test_command: list[str] | None = None
    extra_build_args: list[str] | None = None
    extra_test_args: list[str] | None = None
    pre_build_commands: list[list[str]] | None = None


@dataclass
class VerificationStrategyConfig:
    """Repository-level configuration consumed by the resolver."""

    project_type: str = AUTO_PROJECT_TYPE
    language_overrides: Mapping[str, VerificationCommandOverride] = field(
        default_factory=dict
    )

    @classmethod
    def from_config(cls, config: Any) -> "VerificationStrategyConfig":
        """Build a resolver config from a pydantic model or mapping."""

        if config is None:
            return cls()
        if isinstance(config, cls):
            return config

        if isinstance(config, Mapping):
            project_type = config.get("project_type", AUTO_PROJECT_TYPE)
            raw_overrides = config.get("language_overrides") or {}
        else:
            project_type = getattr(config, "project_type", AUTO_PROJECT_TYPE)
            raw_overrides = getattr(config, "language_overrides", None) or {}

        overrides: dict[str, VerificationCommandOverride] = {}
        for language, raw in dict(raw_overrides).items():
            if isinstance(raw, VerificationCommandOverride):
                overrides[str(language).lower()] = raw
                continue
            if isinstance(raw, Mapping):
                getter = raw.get
            else:

                def getter(key: str, _source: Any = raw) -> Any:
                    return getattr(_source, key, None)

            overrides[str(language).lower()] = VerificationCommandOverride(
                build_command=_as_list(getter("build_command")),
                test_command=_as_list(getter("test_command")),
                extra_build_args=_as_list(getter("extra_build_args")),
                extra_test_args=_as_list(getter("extra_test_args")),
                pre_build_commands=_as_commands(getter("pre_build_commands")),
            )

        return cls(
            project_type=str(project_type or AUTO_PROJECT_TYPE).lower(),
            language_overrides=overrides,
        )


def _as_list(value: Any) -> list[str] | None:
    if not value:
        return None
    return [str(item) for item in value]


def _as_commands(value: Any) -> list[list[str]] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or any(
        not isinstance(command, (list, tuple))
        or not command
        or not all(isinstance(token, str) for token in command)
        or not command[0].strip()
        for command in value
    ):
        raise ValueError(
            "pre_build_commands must contain nonempty command token lists."
        )
    return [list(command) for command in value]


def _expand_tokens(command: Iterable[str], context: VerificationContext) -> list[str]:
    replacements = {
        "{repo_path}": context.repo_path.as_posix(),
        "{junit_xml}": context.junit_xml_path.as_posix(),
        "{coverage_xml}": context.coverage_xml_path.as_posix(),
    }
    expanded: list[str] = []
    for argument in command:
        value = str(argument)
        for token, replacement in replacements.items():
            value = value.replace(token, replacement)
        expanded.append(value)
    return expanded
