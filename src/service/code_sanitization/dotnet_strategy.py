from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from src.service.code_sanitization.verification_strategy import (
    VerificationCommands,
    VerificationCommandStrategy,
    VerificationContext,
)


class DotnetVerificationStrategy(VerificationCommandStrategy):
    """Discover dotnet build/test commands for .NET repositories."""

    project_type: ClassVar[str] = "dotnet"
    languages: ClassVar[frozenset[str]] = frozenset({"c#", "csharp", "dotnet"})

    def matches(self, context: VerificationContext) -> bool:
        return bool(self._solution_candidates(context.repo_path)) or bool(
            next(context.repo_path.rglob("*.csproj"), None)
        )

    def build(self, context: VerificationContext) -> VerificationCommands:
        repo_path = context.repo_path
        owning_projects = self._infer_owning_projects(repo_path, context.changed_files)
        test_projects = self._infer_test_projects(repo_path, owning_projects)

        build_target = self._resolve_build_target(
            repo_path, owning_projects, test_projects
        )
        if build_target is None:
            return VerificationCommands(project_type=self.project_type)

        build_command = [
            "dotnet",
            "build",
            self._as_argument(repo_path, build_target),
            "--nologo",
        ]

        test_command: list[str] | None = None
        if test_projects:
            trx_path = context.junit_xml_path.with_suffix(".trx")
            test_command = [
                "dotnet",
                "test",
                str(test_projects[0].relative_to(repo_path)),
                "--no-build",
                "--nologo",
                "--logger",
                f"trx;LogFileName={trx_path.name}",
                "--results-directory",
                str(trx_path.parent),
            ]

        return VerificationCommands(
            project_type=self.project_type,
            build_command=build_command,
            test_command=test_command,
        )

    def _resolve_build_target(
        self,
        repo_path: Path,
        owning_projects: list[Path],
        test_projects: list[Path],
    ) -> Path | None:
        """Prefer the projects affected by the change over the whole solution.

        Building the full solution pulls in unrelated projects whose pre-existing
        failures mask the generated code, so only the owning projects and their
        test projects are compiled. A single target is passed directly; several
        targets are compiled through a generated MSBuild traversal project.
        """

        targets = list(dict.fromkeys(owning_projects + test_projects))
        if len(targets) == 1:
            return targets[0]
        if targets:
            return self._write_traversal_project(repo_path, targets)

        solution_candidates = self._solution_candidates(repo_path)
        if solution_candidates:
            return solution_candidates[0]
        return next(iter(sorted(repo_path.rglob("*.csproj"))), None)

    @staticmethod
    def _as_argument(repo_path: Path, target: Path) -> str:
        try:
            return str(target.relative_to(repo_path))
        except ValueError:
            return str(target)

    @staticmethod
    def _write_traversal_project(repo_path: Path, targets: list[Path]) -> Path:
        traversal_dir = repo_path / ".experiment_artifacts"
        traversal_dir.mkdir(parents=True, exist_ok=True)
        traversal_path = traversal_dir / "gate-targets.proj"

        includes = "\n".join(
            f'    <GateProject Include="{target}" />' for target in targets
        )
        traversal_path.write_text(
            '<Project DefaultTargets="Build">\n'
            "  <ItemGroup>\n"
            f"{includes}\n"
            "  </ItemGroup>\n"
            '  <Target Name="Restore">\n'
            '    <MSBuild Projects="@(GateProject)" Targets="Restore" />\n'
            "  </Target>\n"
            '  <Target Name="Build">\n'
            '    <MSBuild Projects="@(GateProject)" Targets="Build" '
            'BuildInParallel="true" />\n'
            "  </Target>\n"
            "</Project>\n",
            encoding="utf-8",
        )
        return traversal_path

    @staticmethod
    def _solution_candidates(repo_path: Path) -> list[Path]:
        return sorted(repo_path.glob("*.sln")) + sorted(repo_path.glob("*.slnx"))

    @staticmethod
    def _infer_owning_projects(
        repo_path: Path, changed_files: tuple[str, ...]
    ) -> list[Path]:
        owning_projects: list[Path] = []
        for relative_file in changed_files:
            changed_path = repo_path / relative_file
            if changed_path.suffix.lower() == ".csproj" and changed_path.is_file():
                owning_projects.append(changed_path)
                continue

            current = (repo_path / relative_file).parent
            while current != repo_path and repo_path in current.parents:
                projects = sorted(current.glob("*.csproj"))
                if projects:
                    owning_projects.append(projects[0])
                    break
                current = current.parent

        return list(dict.fromkeys(owning_projects))

    @staticmethod
    def _is_test_project(project: Path) -> bool:
        stem = project.stem.lower()
        if stem.endswith(".tests") or stem.endswith(".test"):
            return True

        try:
            project_text = project.read_text(encoding="utf-8-sig")
        except OSError:
            return False

        return "<istestproject>true</istestproject>" in "".join(
            project_text.lower().split()
        )

    @classmethod
    def _infer_test_projects(
        cls, repo_path: Path, owning_projects: list[Path]
    ) -> list[Path]:
        test_projects: list[Path] = []
        for owning_project in owning_projects:
            # A changed file may already live inside a test project, in which
            # case no sibling lookup would ever find the suite to execute.
            if cls._is_test_project(owning_project):
                test_projects.append(owning_project)
                continue

            parent = owning_project.parent.parent
            stem = owning_project.stem
            patterns = [f"{stem}.Tests*", f"{stem}.Test*"]
            # Projects such as "X.Y.Generators" are usually covered by "X.Y.Tests",
            # so the last name segment is also tried as a suite prefix.
            if "." in stem:
                prefix = stem.rsplit(".", 1)[0]
                patterns.extend([f"{prefix}.Tests*", f"{prefix}.Test*"])

            for pattern in patterns:
                for candidate_dir in sorted(parent.glob(pattern)):
                    test_projects.extend(sorted(candidate_dir.glob("*.csproj")))

        return list(dict.fromkeys(test_projects))
