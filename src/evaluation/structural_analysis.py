from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tokenize
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urljoin, urlparse

import requests
import tomllib
import tree_sitter_c_sharp
from pydantic import Field, model_validator
from tree_sitter import Language, Parser

from src.evaluation.metrics.structural import (
    canonical_hash,
    compare_structural_metrics,
    source_hash,
)
from src.models.structural_metrics import (
    AnalyzedFile,
    AnalyzerReport,
    MetricModel,
    RuleCount,
    StructuralMetricInput,
    StructuralProtocol,
)


class AnalyzerConfig(MetricModel):
    instrument: str = Field(min_length=1)
    kind: Literal["ruff", "roslyn", "sonarqube", "report"]
    enabled: bool = True
    expected_version: str = Field(min_length=1)
    ruleset_id: str = Field(min_length=1)
    ruleset_version: str = Field(min_length=1)
    command: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=300, ge=1)
    before_report: str | None = None
    after_report: str | None = None
    sonar_url: str | None = None
    sonar_project: str | None = None
    sonar_token_env: str = "SONAR_TOKEN"
    sonar_before_branch: str | None = None
    sonar_after_branch: str | None = None

    @model_validator(mode="after")
    def configured(self) -> AnalyzerConfig:
        if not self.enabled:
            return self
        if self.kind == "report" and not (self.before_report and self.after_report):
            raise ValueError(
                "Report collection requires both before_report and after_report."
            )
        if self.kind == "roslyn" and (
            not self.command or not any("{report}" in item for item in self.command)
        ):
            raise ValueError(
                "Roslyn requires an explicit build command containing {report}."
            )
        if self.kind == "sonarqube" and not all(
            (
                self.sonar_url,
                self.sonar_project,
                self.sonar_before_branch,
                self.sonar_after_branch,
            )
        ):
            raise ValueError(
                "SonarQube requires URL, project and both analysis branches."
            )
        return self


class StructuralAnalysisConfig(MetricModel):
    protocol: StructuralProtocol
    analyzers: list[AnalyzerConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def instruments(self) -> StructuralAnalysisConfig:
        names = [a.instrument for a in self.analyzers if a.enabled]
        if len(set(names)) != len(names):
            raise ValueError("Configured analyzer instrument IDs must be unique.")
        if set(names) != {rule.instrument for rule in self.protocol.rules}:
            raise ValueError(
                "Enabled analyzers must exactly cover the registered protocol."
            )
        return self


def _repository_files(repo: Path):
    for root, dirs, files in os.walk(repo):
        dirs[:] = sorted(
            name
            for name in dirs
            if name
            not in {
                ".git",
                "bin",
                "obj",
                ".venv",
                "venv",
                "node_modules",
                ".idea",
                "__pycache__",
            }
        )
        for name in sorted(files):
            yield Path(root) / name


def _configuration_files(repo: Path) -> dict[str, str]:
    names = {
        "pyproject.toml",
        "ruff.toml",
        ".ruff.toml",
        ".editorconfig",
        "Directory.Build.props",
        "Directory.Build.targets",
        "Directory.Packages.props",
        "global.json",
        "NuGet.Config",
    }
    return {
        path.relative_to(repo).as_posix(): source_hash(path.read_text(encoding="utf-8"))
        for path in _repository_files(repo)
        if path.name in names or path.suffix in {".csproj", ".ruleset"}
    }


def discover_analyzers(repo: Path) -> list[dict[str, str]]:
    """Report configuration evidence only; discovery never executes repository code."""
    found = []
    for name in ("ruff.toml", ".ruff.toml", "pyproject.toml"):
        path = repo / name
        if not path.is_file():
            continue
        if name == "pyproject.toml":
            with path.open("rb") as stream:
                if "ruff" not in tomllib.load(stream).get("tool", {}):
                    continue
        found.append({"kind": "ruff", "configuration": name})
    for path in _repository_files(repo):
        if path.suffix == ".csproj":
            found.append(
                {"kind": "roslyn", "configuration": path.relative_to(repo).as_posix()}
            )
    for name in ("sonar-project.properties", "SonarQube.Analysis.xml"):
        if (repo / name).is_file():
            found.append({"kind": "sonarqube", "configuration": name})
    return found


def _sloc(path: str, source: str) -> int:
    if path.endswith(".py"):
        rows: set[int] = set()
        excluded = {
            tokenize.COMMENT,
            tokenize.NL,
            tokenize.NEWLINE,
            tokenize.INDENT,
            tokenize.DEDENT,
            tokenize.ENDMARKER,
            tokenize.ENCODING,
        }
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type not in excluded:
                rows.update(range(token.start[0], token.end[0] + 1))
        return len(rows)
    if path.endswith(".cs"):
        tree = Parser(Language(tree_sitter_c_sharp.language())).parse(source.encode())
        if tree.root_node.has_error:
            raise ValueError(
                f"Cannot count C# SLOC for syntactically invalid source: {path}"
            )
        rows = set()
        stack = [tree.root_node]
        while stack:
            node = stack.pop()
            if node.type == "comment":
                continue
            if node.children:
                stack.extend(node.children)
            elif node.end_byte > node.start_byte:
                end = node.end_point.row - int(node.end_point.column == 0)
                rows.update(range(node.start_point.row, end + 1))
        return len(rows)
    raise ValueError(f"No live SLOC instrument for {path}; use a normalized report.")


def _run(command: list[str], repo: Path, timeout: int) -> subprocess.CompletedProcess:
    result = subprocess.run(
        command,
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(
            f"Analyzer failed ({result.returncode}): {result.stderr or result.stdout}"
        )
    return result


def _finding_path(value: str, repo: Path, *, uri: bool = False) -> str:
    if value.startswith("file:"):
        value = unquote(urlparse(value).path)
        if (
            os.name == "nt"
            and value.startswith("/")
            and len(value) > 2
            and value[2] == ":"
        ):
            value = value[1:]
    elif uri:
        if urlparse(value).scheme:
            raise ValueError("SARIF source locations must refer to local files.")
        value = unquote(value)
    path = Path(value)
    if path.is_absolute():
        return path.resolve().relative_to(repo.resolve()).as_posix()
    return path.as_posix()


def _sarif_path(location: dict, run: dict, repo: Path) -> str:
    if "uri" not in location and "index" in location:
        location = run["artifacts"][location["index"]]["location"]
    value = location["uri"]
    if "uriBaseId" in location:
        base = run["originalUriBaseIds"][location["uriBaseId"]]
        if "uriBaseId" in base:
            raise ValueError("Nested SARIF URI bases require a normalized report.")
        value = urljoin(base["uri"], value)
    return _finding_path(value, repo, uri=True)


def _loc_versions(sources: dict[str, str]) -> dict[str, str]:
    versions = {"sloc-python-runtime": sys.version.split()[0]}
    if any(path.endswith(".cs") for path in sources):
        versions.update(
            {
                "sloc-tree-sitter": package_version("tree-sitter"),
                "sloc-tree-sitter-c-sharp": package_version("tree-sitter-c-sharp"),
            }
        )
    return versions


def _sarif_versions(payload: dict) -> dict[str, str]:
    versions = {}
    for run in payload["runs"]:
        for component in [run["tool"]["driver"], *run["tool"].get("extensions", [])]:
            key = component["name"]
            version = component.get("semanticVersion") or component.get("version")
            if not version or (key in versions and versions[key] != version):
                raise ValueError(
                    "SARIF tool components must declare consistent instrument versions."
                )
            versions[key] = version
    return versions


def _native_counts(
    payload: object,
    kind: str,
    repo: Path,
    scope: set[str],
    rules: set[str],
    expected_version: str,
) -> list[RuleCount]:
    counts: Counter = Counter()
    if kind == "ruff":
        if not isinstance(payload, list):
            raise ValueError("Ruff must return a JSON findings array.")
        for item in payload:
            path = _finding_path(item["filename"], repo)
            if path in scope:
                if item["code"] not in rules:
                    raise ValueError(f"Unmapped Ruff rule: {item['code']}")
                counts[(item["code"], path)] += 1
    else:
        if not isinstance(payload, dict) or payload.get("version") != "2.1.0":
            raise ValueError("Roslyn requires a SARIF 2.1.0 report.")
        seen_rules: set[str] = set()
        for run in payload["runs"]:
            driver = run["tool"]["driver"]
            if (
                driver.get("semanticVersion") or driver.get("version")
            ) != expected_version:
                raise ValueError(
                    "Roslyn SARIF instrument version differs from the pinned version."
                )
            seen_rules.update(
                rule["id"]
                for component in [driver, *run["tool"].get("extensions", [])]
                for rule in component.get("rules", [])
            )
            for component in [driver, *run["tool"].get("extensions", [])]:
                for rule in component.get("rules", []):
                    configuration = rule.get("defaultConfiguration", {})
                    if rule["id"] in rules and (
                        configuration.get("enabled") is False
                        or configuration.get("level") == "none"
                    ):
                        raise ValueError(
                            "A registered SARIF rule is disabled; import effective-rule coverage in a normalized report."
                        )
            artifacts = {
                _sarif_path(item["location"], run, repo)
                for item in run.get("artifacts", [])
                if "location" in item and "uri" in item["location"]
            }
            if not scope <= artifacts:
                raise ValueError(
                    "SARIF does not attest all target files; import a normalized report with explicit coverage."
                )
            if not run.get("invocations") or any(
                invocation.get("executionSuccessful") is not True
                for invocation in run["invocations"]
            ):
                raise ValueError("SARIF must attest successful analyzer execution.")
            for invocation in run["invocations"]:
                if any(
                    note.get("level") == "error"
                    for note in invocation.get("toolExecutionNotifications", [])
                ):
                    raise ValueError("SARIF contains analyzer execution errors.")
                for override in invocation.get("ruleConfigurationOverrides", []):
                    if override["descriptor"]["id"] in rules and (
                        override["configuration"].get("enabled") is False
                        or override["configuration"].get("level") == "none"
                    ):
                        raise ValueError(
                            "A registered SARIF rule is disabled by the invocation."
                        )
            for item in run.get("results", []):
                if (
                    item.get("kind", "fail") != "fail"
                    or item.get("baselineState") == "absent"
                ):
                    raise ValueError(
                        "SARIF must contain current violation results, not pass or absent-baseline entries."
                    )
                locations = item.get("locations", [])
                if not locations:
                    raise ValueError(
                        "Cannot attribute a SARIF finding without a file location."
                    )
                path = _sarif_path(
                    locations[0]["physicalLocation"]["artifactLocation"], run, repo
                )
                if path in scope:
                    if item["ruleId"] not in rules:
                        raise ValueError(f"Unmapped Roslyn rule: {item['ruleId']}")
                    if item.get("suppressions"):
                        raise ValueError(
                            "Suppressed SARIF findings require an explicit protocol."
                        )
                    counts[(item["ruleId"], path)] += 1
        if not rules <= seen_rules:
            raise ValueError("SARIF does not attest all registered analyzer rules.")
    return [
        RuleCount(rule_id=rule, path=path, count=count)
        for (rule, path), count in sorted(counts.items())
    ]


def _sonar_report(
    config: AnalyzerConfig,
    stage: str,
    sources: dict[str, str],
    rules: set[str],
) -> AnalyzerReport:
    token = os.environ.get(config.sonar_token_env)
    if not token:
        raise ValueError(
            f"Missing SonarQube credential environment variable {config.sonar_token_env}."
        )
    branch = (
        config.sonar_before_branch if stage == "before" else config.sonar_after_branch
    )
    with requests.Session() as session:
        session.auth = (token, "")

        def get(endpoint: str, **params):
            response = session.get(
                f"{config.sonar_url.rstrip('/')}/api/{endpoint}",
                params=params,
                timeout=config.timeout_seconds,
            )
            response.raise_for_status()
            return response

        version = get("server/version").text.strip()
        if version != config.expected_version:
            raise ValueError(
                "SonarQube server version differs from the pinned version."
            )
        analysis_payload = get(
            "project_analyses/search",
            project=config.sonar_project,
            branch=branch,
            p=1,
            ps=1,
        ).json()
        if not analysis_payload.get("analyses"):
            raise ValueError(
                "SonarQube has no completed analysis for the configured snapshot."
            )
        analysis = analysis_payload["analyses"][0]
        analyzed_at = datetime.fromisoformat(analysis["date"].replace("Z", "+00:00"))
        plugins = get("plugins/installed").json()["plugins"]
        profiles = get("qualityprofiles/search", project=config.sonar_project).json()[
            "profiles"
        ]
        active: set[str] = set()
        profile_fingerprints = []
        for profile in sorted(profiles, key=lambda item: item["key"]):
            if (
                not profile.get("rulesUpdatedAt")
                or datetime.fromisoformat(
                    profile["rulesUpdatedAt"].replace("Z", "+00:00")
                )
                > analyzed_at
            ):
                raise ValueError(
                    "SonarQube profile was changed after analysis or lacks version evidence."
                )
            page = 1
            profile_rules = []
            while True:
                payload = get(
                    "rules/search",
                    qprofile=profile["key"],
                    activation="true",
                    p=page,
                    ps=500,
                ).json()
                if not payload["rules"] and len(profile_rules) < payload["total"]:
                    raise ValueError(
                        "SonarQube returned an incomplete active-rule page."
                    )
                profile_rules.extend(payload["rules"])
                if page * 500 >= payload["total"]:
                    break
                page += 1
            active.update(rule["key"] for rule in profile_rules)
            profile_fingerprints.append(
                {
                    "key": profile["key"],
                    "rules": sorted(profile_rules, key=lambda rule: rule["key"]),
                }
            )
        if not rules <= active:
            raise ValueError(
                "SonarQube quality profiles do not enable all registered rules."
            )
        files = []
        counts: Counter = Counter()
        for path, source in sources.items():
            component = f"{config.sonar_project}:{path}"
            remote = get("sources/raw", key=component, branch=branch).text
            if source_hash(remote) != source_hash(source):
                raise ValueError(f"Stale SonarQube source for {stage}: {path}")
            files.append(
                AnalyzedFile(
                    path=path, sha256=source_hash(source), loc=_sloc(path, source)
                )
            )
            page = 1
            while True:
                payload = get(
                    "issues/search",
                    componentKeys=component,
                    branch=branch,
                    rules=",".join(sorted(rules)),
                    resolved="false",
                    p=page,
                    ps=500,
                ).json()
                for issue in payload["issues"]:
                    if issue["component"] != component or issue["rule"] not in rules:
                        raise ValueError(
                            "SonarQube returned a finding outside the requested scope."
                        )
                    counts[(issue["rule"], path)] += 1
                page_size = payload["paging"]["pageSize"]
                if (
                    not payload["issues"]
                    and (page - 1) * page_size < payload["paging"]["total"]
                ):
                    raise ValueError("SonarQube returned an incomplete findings page.")
                if page * page_size >= payload["paging"]["total"]:
                    break
                if page * page_size >= 10000:
                    raise ValueError(
                        "SonarQube issue search limit prevents complete collection."
                    )
                page += 1
        latest = get(
            "project_analyses/search",
            project=config.sonar_project,
            branch=branch,
            p=1,
            ps=1,
        ).json()["analyses"][0]
        if latest["key"] != analysis["key"]:
            raise ValueError("SonarQube analysis changed during collection.")
        return AnalyzerReport(
            instrument=config.instrument,
            instrument_version=version,
            instrument_details={
                **{f"plugin:{plugin['key']}": plugin["version"] for plugin in plugins},
                **_loc_versions(sources),
            },
            ruleset_id=config.ruleset_id,
            ruleset_version=config.ruleset_version,
            configuration_sha256=canonical_hash(
                {
                    "profiles": profile_fingerprints,
                    "plugins": sorted(plugins, key=lambda plugin: plugin["key"]),
                    "collector": "structural-analysis-v1",
                    "query": {"resolved": False, "rules": sorted(rules)},
                }
            ),
            timestamp=analyzed_at,
            loc_method="syntax-noncomment-lines-v1",
            source=f"{config.sonar_project}@{branch}:analysis:{analysis['key']}",
            files=files,
            analyzed_rules=sorted(rules),
            counts=[
                RuleCount(rule_id=r, path=p, count=n)
                for (r, p), n in sorted(counts.items())
            ],
        )


def collect_reports(
    config: StructuralAnalysisConfig,
    stage: Literal["before", "after"],
    repo: Path,
    sources: dict[str, str],
    config_dir: Path,
) -> list[AnalyzerReport]:
    reports = []
    for analyzer in config.analyzers:
        if not analyzer.enabled:
            continue
        rules = {
            r.rule_id
            for r in config.protocol.rules
            if r.instrument == analyzer.instrument
        }
        if analyzer.kind != "report" and any(
            rule.unit != "occurrences"
            for rule in config.protocol.rules
            if rule.instrument == analyzer.instrument
        ):
            raise ValueError(
                "Live issue collectors count occurrences, not duplicated lines; import a normalized line-count report."
            )
        if analyzer.kind == "report":
            path = (
                analyzer.before_report if stage == "before" else analyzer.after_report
            )
            report = AnalyzerReport.model_validate_json(
                (config_dir / path).read_text(encoding="utf-8")
            )
            if (
                report.instrument != analyzer.instrument
                or report.instrument_version != analyzer.expected_version
                or report.ruleset_id != analyzer.ruleset_id
                or report.ruleset_version != analyzer.ruleset_version
            ):
                raise ValueError(
                    "Imported report provenance differs from analyzer configuration."
                )
        elif analyzer.kind == "sonarqube":
            report = _sonar_report(analyzer, stage, sources, rules)
        else:
            suffix = ".py" if analyzer.kind == "ruff" else ".cs"
            if any(not path.endswith(suffix) for path in sources):
                raise ValueError(
                    f"{analyzer.kind} cannot cover the full block scope; split the block."
                )
            files = [
                AnalyzedFile(path=p, sha256=source_hash(s), loc=_sloc(p, s))
                for p, s in sorted(sources.items())
            ]
            for path, source in sources.items():
                if (repo / path).read_bytes() != source.encode("utf-8"):
                    raise ValueError(
                        f"Analyzer input does not match the requested source snapshot: {path}"
                    )
            configuration = _configuration_files(repo)
            if analyzer.kind == "ruff":
                command = analyzer.command or [sys.executable, "-m", "ruff"]
                version = _run([*command, "--version"], repo, analyzer.timeout_seconds)
                if (
                    version.returncode != 0
                    or version.stdout.strip() != f"ruff {analyzer.expected_version}"
                ):
                    raise ValueError("Ruff version differs from the pinned version.")
                result = _run(
                    [
                        *command,
                        "check",
                        "--no-cache",
                        "--output-format",
                        "json",
                        "--select",
                        ",".join(sorted(rules)),
                        "--ignore-noqa",
                        "--config",
                        "lint.ignore = []",
                        "--config",
                        "lint.extend-ignore = []",
                        "--config",
                        "lint.extend-select = []",
                        "--config",
                        "lint.per-file-ignores = {}",
                        "--config",
                        "lint.extend-per-file-ignores = {}",
                        "--config",
                        "force-exclude = false",
                        *sorted(sources),
                    ],
                    repo,
                    analyzer.timeout_seconds,
                )
                payload = json.loads(result.stdout)
                if result.returncode == 1 and not payload:
                    raise RuntimeError(f"Ruff failed without findings: {result.stderr}")
            else:
                report_path = repo / ".structural-analysis.sarif"
                if report_path.exists():
                    raise ValueError("Refusing to overwrite an existing SARIF report.")
                command = [
                    item.replace("{repo_path}", str(repo)).replace(
                        "{report}", str(report_path)
                    )
                    for item in analyzer.command
                ]
                result = _run(command, repo, analyzer.timeout_seconds)
                try:
                    payload = json.loads(report_path.read_text(encoding="utf-8-sig"))
                finally:
                    report_path.unlink(missing_ok=True)
                if result.returncode:
                    raise RuntimeError(
                        f"Roslyn build failed: {result.stdout}\n{result.stderr}"
                    )
            report = AnalyzerReport(
                instrument=analyzer.instrument,
                instrument_version=analyzer.expected_version,
                instrument_details={
                    **_loc_versions(sources),
                    **(_sarif_versions(payload) if analyzer.kind == "roslyn" else {}),
                },
                ruleset_id=analyzer.ruleset_id,
                ruleset_version=analyzer.ruleset_version,
                configuration_sha256=canonical_hash(
                    {
                        "files": configuration,
                        "command": analyzer.command,
                        "collector": "structural-analysis-v1",
                        "kind": analyzer.kind,
                        "registered_rules": sorted(rules),
                        "ruff_suppression_policy": "ignore-noqa-and-clear-rule-ignores-v1",
                    }
                ),
                timestamp=datetime.now(timezone.utc),
                loc_method="syntax-noncomment-lines-v1",
                source=f"live-{analyzer.kind}:{stage}",
                files=files,
                analyzed_rules=sorted(rules),
                counts=_native_counts(
                    payload,
                    analyzer.kind,
                    repo,
                    set(sources),
                    rules,
                    analyzer.expected_version,
                ),
            )
        reports.append(report)
        if analyzer.kind not in {"report", "sonarqube"}:
            for path, source in sources.items():
                if (repo / path).read_bytes() != source.encode("utf-8"):
                    raise ValueError(
                        f"Analyzer modified source during collection: {path}"
                    )
            if _configuration_files(repo) != configuration:
                raise ValueError(
                    "Analyzer modified ruleset configuration during collection."
                )
    return reports


def metric_input(
    config: StructuralAnalysisConfig,
    before: list[AnalyzerReport],
    after: list[AnalyzerReport],
) -> StructuralMetricInput:
    return StructuralMetricInput(protocol=config.protocol, before=before, after=after)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Discover analyzer configuration or evaluate pre-registered M-1 evidence."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--discover-repo", type=Path)
    mode.add_argument(
        "--config-schema",
        action="store_true",
        help="Export the validated analyzer/protocol configuration JSON Schema.",
    )
    mode.add_argument(
        "--input",
        type=Path,
        help="StructuralMetricInput JSON containing protocol and before/after reports.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-regression", action="store_true")
    args = parser.parse_args(argv)
    result = None
    if args.config_schema:
        payload = StructuralAnalysisConfig.model_json_schema()
    elif args.discover_repo:
        if not args.discover_repo.is_dir():
            parser.error("--discover-repo must be an existing repository directory.")
        payload = {
            "discovered": discover_analyzers(args.discover_repo),
            "execution": "not-requested",
        }
    else:
        inputs = StructuralMetricInput.model_validate_json(
            args.input.read_text(encoding="utf-8")
        )
        result = compare_structural_metrics(inputs)
        payload = result.model_dump(mode="json")
    text = json.dumps(payload, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return int(
        args.fail_on_regression
        and result is not None
        and result.effectiveness_verdict == "regressed"
    )


if __name__ == "__main__":
    raise SystemExit(main())
