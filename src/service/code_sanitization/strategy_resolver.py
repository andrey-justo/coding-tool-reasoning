"""Select verification strategies independently of their shared interfaces."""

from __future__ import annotations

from typing import Any, Sequence

from src.service.code_sanitization.dotnet_strategy import DotnetVerificationStrategy
from src.service.code_sanitization.python_strategy import PythonVerificationStrategy
from src.service.code_sanitization.verification_strategy import (
    AUTO_PROJECT_TYPE,
    NONE_PROJECT_TYPE,
    VerificationCommandOverride,
    VerificationCommands,
    VerificationCommandStrategy,
    VerificationContext,
    VerificationStrategyConfig,
    _expand_tokens,
)


class VerificationStrategyResolver:
    """Pick the verification strategy for a repository and apply overrides."""

    def __init__(
        self,
        strategies: Sequence[VerificationCommandStrategy] | None = None,
        config: Any = None,
    ) -> None:
        self._strategies = (
            list(strategies)
            if strategies
            else [PythonVerificationStrategy(), DotnetVerificationStrategy()]
        )
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
