from __future__ import annotations

from pathlib import Path

from src.service.code_sanitization import (
    VerificationContext,
    VerificationStrategyResolver,
)


def _context(repo: Path, changed: tuple[str, ...] = (), language: str | None = None):
    artifacts = repo / ".experiment_artifacts"
    return VerificationContext(
        repo_path=repo,
        junit_xml_path=artifacts / "junit.xml",
        coverage_xml_path=artifacts / "coverage.xml",
        changed_files=changed,
        language=language,
    )


def _make_python_repo(root: Path) -> Path:
    repo = root / "py"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    return repo


def _make_dotnet_repo(root: Path) -> Path:
    repo = root / "net"
    (repo / "src" / "Core").mkdir(parents=True)
    (repo / "src" / "Core.Tests").mkdir(parents=True)
    (repo / "Product.slnx").write_text("<Solution />", encoding="utf-8")
    (repo / "src" / "Core" / "Core.csproj").write_text("<Project />", encoding="utf-8")
    (repo / "src" / "Core.Tests" / "Core.Tests.csproj").write_text(
        "<Project />", encoding="utf-8"
    )
    return repo


def test_resolver_prefers_strategy_matching_changed_file_language(
    tmp_path: Path,
) -> None:
    repo = _make_dotnet_repo(tmp_path)
    # A polyglot repository that would otherwise match the Python strategy first.
    (repo / "tests").mkdir()

    resolved = VerificationStrategyResolver().resolve(
        _context(repo, changed=("src/Core/Changed.cs",), language="c#")
    )

    assert resolved.project_type == "dotnet"
    assert resolved.build_command[:2] == ["dotnet", "build"]


def test_resolver_falls_back_to_declaration_order_without_language(
    tmp_path: Path,
) -> None:
    repo = _make_python_repo(tmp_path)
    resolved = VerificationStrategyResolver().resolve(_context(repo))

    assert resolved.project_type == "python"


def test_resolver_returns_unknown_for_unrecognized_repository(tmp_path: Path) -> None:
    repo = tmp_path / "empty"
    repo.mkdir()
    resolved = VerificationStrategyResolver().resolve(_context(repo))

    assert resolved.project_type == "unknown"
    assert resolved.build_command is None
    assert resolved.test_command is None


def test_configured_project_type_none_skips_verification(tmp_path: Path) -> None:
    repo = _make_python_repo(tmp_path)
    resolved = VerificationStrategyResolver(config={"project_type": "none"}).resolve(
        _context(repo)
    )

    assert resolved.project_type == "unknown"
    assert resolved.build_command is None


def test_configured_project_type_forces_strategy(tmp_path: Path) -> None:
    repo = _make_dotnet_repo(tmp_path)
    resolved = VerificationStrategyResolver(config={"project_type": "dotnet"}).resolve(
        _context(repo, changed=("src/Core/Changed.cs",))
    )

    assert resolved.project_type == "dotnet"
    assert "src\\Core.Tests\\Core.Tests.csproj" in resolved.test_command or (
        "src/Core.Tests/Core.Tests.csproj" in resolved.test_command
    )


def test_extra_args_are_appended_to_discovered_commands(tmp_path: Path) -> None:
    repo = _make_dotnet_repo(tmp_path)
    config = {
        "project_type": "auto",
        "language_overrides": {
            "c#": {"extra_build_args": ["-p:WarningsNotAsErrors=NU1902"]}
        },
    }

    resolved = VerificationStrategyResolver(config=config).resolve(
        _context(repo, changed=("src/Core/Changed.cs",), language="c#")
    )

    assert resolved.build_command[:2] == ["dotnet", "build"]
    assert "gate-targets.proj" in resolved.build_command[2]
    assert resolved.build_command[-1] == "-p:WarningsNotAsErrors=NU1902"


def test_dotnet_build_targets_affected_projects_instead_of_solution(
    tmp_path: Path,
) -> None:
    repo = _make_dotnet_repo(tmp_path)

    VerificationStrategyResolver().resolve(
        _context(repo, changed=("src/Core/Changed.cs",), language="c#")
    )

    traversal = repo / ".experiment_artifacts" / "gate-targets.proj"
    assert traversal.exists()
    content = traversal.read_text(encoding="utf-8")
    assert "Core.csproj" in content
    assert "Core.Tests.csproj" in content
    assert "Product.slnx" not in content


def test_dotnet_build_falls_back_to_solution_without_changed_files(
    tmp_path: Path,
) -> None:
    repo = _make_dotnet_repo(tmp_path)

    resolved = VerificationStrategyResolver(config={"project_type": "dotnet"}).resolve(
        _context(repo, language="c#")
    )

    assert "Product.slnx" in resolved.build_command


def test_language_override_replaces_commands_and_expands_tokens(
    tmp_path: Path,
) -> None:
    repo = _make_python_repo(tmp_path)
    config = {
        "project_type": "auto",
        "language_overrides": {
            "python": {
                "build_command": ["make", "build"],
                "test_command": ["make", "test", "--junit={junit_xml}"],
            }
        },
    }

    resolved = VerificationStrategyResolver(config=config).resolve(_context(repo))

    assert resolved.project_type == "python"
    assert resolved.build_command == ["make", "build"]
    assert resolved.test_command[-1].endswith("junit.xml")
    assert "{junit_xml}" not in resolved.test_command[-1]


def test_dotnet_strategy_runs_tests_when_changed_file_is_in_a_test_project(
    tmp_path: Path,
) -> None:
    repo = _make_dotnet_repo(tmp_path)

    resolved = VerificationStrategyResolver().resolve(
        _context(repo, changed=("src/Core.Tests/NewSpec.cs",), language="c#")
    )

    assert resolved.test_command is not None
    assert resolved.test_command[:2] == ["dotnet", "test"]
    assert "Core.Tests" in resolved.test_command[2]


def test_dotnet_strategy_builds_and_tests_the_exact_changed_test_project(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "net-exact"
    project_dir = repo / "tests" / "Component"
    project_dir.mkdir(parents=True)
    project_file = project_dir / "Component.csproj"
    project_file.write_text(
        "<Project><PropertyGroup><IsTestProject>true</IsTestProject></PropertyGroup></Project>",
        encoding="utf-8",
    )
    (project_dir / "Spec.cs").write_text("class Spec {}", encoding="utf-8")

    resolved = VerificationStrategyResolver().resolve(
        _context(
            repo,
            changed=("tests/Component/Component.csproj",),
            language="c#",
        )
    )

    assert resolved.build_command is not None
    assert "tests\\Component\\Component.csproj" in resolved.build_command[2] or (
        "tests/Component/Component.csproj" in resolved.build_command[2]
    )
    assert resolved.test_command is not None
    assert resolved.test_command[0:3] == [
        "dotnet",
        "test",
        resolved.build_command[2],
    ]


def test_dotnet_strategy_recognizes_test_project_by_is_test_project_property(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "net-property"
    project_dir = repo / "tests" / "Component"
    project_dir.mkdir(parents=True)
    project_file = project_dir / "Component.csproj"
    project_file.write_text(
        "<Project><PropertyGroup><IsTestProject>true</IsTestProject></PropertyGroup></Project>",
        encoding="utf-8",
    )
    (project_dir / "Spec.cs").write_text("class Spec {}", encoding="utf-8")

    resolved = VerificationStrategyResolver().resolve(
        _context(repo, changed=("tests/Component/Spec.cs",), language="c#")
    )

    assert resolved.test_command is not None
    assert "Component.csproj" in resolved.test_command[2]


def test_dotnet_strategy_matches_suite_by_project_name_prefix(tmp_path: Path) -> None:
    repo = tmp_path / "net-prefix"
    (repo / "src" / "Akka.Serialization.V2.Generators").mkdir(parents=True)
    (repo / "src" / "Akka.Serialization.V2.Tests").mkdir(parents=True)
    (repo / "Product.slnx").write_text("<Solution />", encoding="utf-8")
    (
        repo
        / "src"
        / "Akka.Serialization.V2.Generators"
        / "Akka.Serialization.V2.Generators.csproj"
    ).write_text("<Project />", encoding="utf-8")
    (
        repo
        / "src"
        / "Akka.Serialization.V2.Tests"
        / "Akka.Serialization.V2.Tests.csproj"
    ).write_text("<Project />", encoding="utf-8")

    resolved = VerificationStrategyResolver().resolve(
        _context(
            repo,
            changed=("src/Akka.Serialization.V2.Generators/Generator.cs",),
            language="c#",
        )
    )

    assert resolved.test_command is not None
    assert "Akka.Serialization.V2.Tests" in resolved.test_command[2]
