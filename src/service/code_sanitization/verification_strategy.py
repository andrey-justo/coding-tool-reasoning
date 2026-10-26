"""Strategy-based discovery of build/test verification commands.

Strategies are selected from repository configuration plus the language inferred
from the changed files, so verification is not hardcoded into the gate tool.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Iterable, Mapping, Sequence

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_type": self.project_type,
            "build_command": self.build_command,
            "test_command": self.test_command,
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
            )

        return cls(
            project_type=str(project_type or AUTO_PROJECT_TYPE).lower(),
            language_overrides=overrides,
        )


class VerificationStrategyResolver:
    """Pick the verification strategy for a repository and apply overrides."""

    def __init__(
        self,
        strategies: Sequence[VerificationCommandStrategy] | None = None,
        config: Any = None,
    ) -> None:
        self._strategies = list(strategies) if strategies else _default_strategies()
        self._config = VerificationStrategyConfig.from_config(config)

    def resolve(self, context: VerificationContext) -> VerificationCommands:
        configured_type = self._config.project_type
        if configured_type == NONE_PROJECT_TYPE:
            return VerificationCommands()

        strategy: VerificationCommandStrategy | None
        if configured_type and configured_type != AUTO_PROJECT_TYPE:
            strategy = next(
                (
                    item
                    for item in self._strategies
                    if item.project_type == configured_type
                ),
                None,
            )
        else:
            strategy = self._select_by_language(context)

        if strategy is None:
            return VerificationCommands()

        commands = strategy.build(context)
        return self._apply_overrides(commands, strategy, context)

    def _select_by_language(
        self, context: VerificationContext
    ) -> VerificationCommandStrategy | None:
        candidates = [item for item in self._strategies if item.matches(context)]
        if not candidates:
            return None

        language = (context.language or "").lower()
        if language:
            for candidate in candidates:
                if language in candidate.languages:
                    return candidate

        return candidates[0]

    def _apply_overrides(
        self,
        commands: VerificationCommands,
        strategy: VerificationCommandStrategy,
        context: VerificationContext,
    ) -> VerificationCommands:
        override = self._lookup_override(strategy, context)
        if override is None:
            return commands

        build_command = (
            _expand_tokens(override.build_command, context)
            if override.build_command
            else commands.build_command
        )
        test_command = (
            _expand_tokens(override.test_command, context)
            if override.test_command
            else commands.test_command
        )

        if build_command and override.extra_build_args:
            build_command = build_command + _expand_tokens(
                override.extra_build_args, context
            )
        if test_command and override.extra_test_args:
            test_command = test_command + _expand_tokens(
                override.extra_test_args, context
            )

        return VerificationCommands(
            project_type=commands.project_type,
            build_command=build_command,
            test_command=test_command,
        )

    def _lookup_override(
        self,
        strategy: VerificationCommandStrategy,
        context: VerificationContext,
    ) -> VerificationCommandOverride | None:
        overrides = self._config.language_overrides
        if not overrides:
            return None

        keys: list[str] = []
        if context.language:
            keys.append(context.language.lower())
        keys.extend(sorted(strategy.languages))
        keys.append(strategy.project_type)

        for key in keys:
            override = overrides.get(key)
            if override is not None:
                return override
        return None


def _as_list(value: Any) -> list[str] | None:
    if not value:
        return None
    return [str(item) for item in value]


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


def _default_strategies() -> list[VerificationCommandStrategy]:
    from src.service.code_sanitization.dotnet_strategy import DotnetVerificationStrategy
    from src.service.code_sanitization.python_strategy import PythonVerificationStrategy

    return [PythonVerificationStrategy(), DotnetVerificationStrategy()]
