# Python Code Reasoning Tools

[![CI](https://github.com/andrey-justo/coding-tool-reasoning/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/andrey-justo/coding-tool-reasoning/actions/workflows/ci.yml)
[![CD](https://github.com/andrey-justo/coding-tool-reasoning/actions/workflows/cd.yml/badge.svg?branch=master)](https://github.com/andrey-justo/coding-tool-reasoning/actions/workflows/cd.yml)

## Setting up the Environment

The project includes setup scripts for both PowerShell (Windows) and bash (Unix-like systems) environments.

### Windows (PowerShell)
```pwsh
.\setup\setup.ps1
```

To activate the environment later:
```pwsh
.venv\Scripts\Activate.ps1
```

### Unix-like Systems (bash)
```bash
# Make scripts executable (one-time)
chmod +x ./setup/*.sh

# Run setup
./setup/setup.sh
```

To activate the environment later:
```bash
source .venv/bin/activate
```

To deactivate the environment (both PowerShell and bash):
```shell
deactivate
```

Both setup scripts will:
- Create a virtual environment in `.venv`
- Activate the environment
- Upgrade pip
- Install all dependencies from `requirements.txt`

## Install PyTorch

### CUDA
```shell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
```

### CPU
```shell
pip install torch torchvision
```

## Copilot SDK provider

The `CopilotSDK` provider uses the Copilot runtime's authenticated account,
independently of Git push credentials. It does not need an Azure API key or
reuse the VS Code chat connection. Install dependencies with `poetry install`,
then authenticate Copilot CLI with `copilot login` if necessary. The SDK can
download its pinned runtime automatically; `COPILOT_CLI_PATH` can select an
existing compatible runtime instead.

Discover models authorized for the account:

```powershell
poetry run python -m src.main copilot-models
```

The configured alias `copilot-gpt-5.3-codex` selects the SDK model
`gpt-5.3-codex`; Azure's existing `gpt-5.3-codex` entry remains unchanged.
Additional entries in `available_models.yaml` can use `provider: CopilotSDK`,
`model_name` (the experiment alias), `sdk_model` (a discovered model ID), and
`timeout` in seconds. Model discovery is not a guarantee of remaining quota.

Copilot requests share one runtime and background event loop per process, avoiding
repeated CLI startup. Each request still uses a fresh text-only session with tools, repository instruction
discovery, hooks, and skills disabled. SDK sessions run in a temporary directory
and cannot approve tool permissions. Only completed root final-answer messages
are returned; commentary and subagent messages are not generation results.
An empty completion is retried once in a fresh session, with an explicit warning
and one shared request timeout. A second empty completion remains an error.
The session system message requests direct text output rather than agent actions.
Temperature, seed, and other generation
keyword arguments are not supported by this adapter and produce an explicit
warning; do not interpret these runs as temperature/seed-controlled or directly
equivalent to Azure runs.

`execution.max_generation_concurrency` in `swe_mcp_config.yaml` controls bounded
parallel generation and build-repair chunks (1-8, schema default 1). This checkout
sets it to 3. Only chunks within the same file are parallelized;
results are assembled in their original order, and existing syntax checks,
fallback reporting, and repair budgets are retained. The Copilot provider supports
parallel sessions; other providers remain serial. Set the value to 1 for serial
execution or to avoid concurrent quota pressure.

Runtime logs include request IDs and elapsed times, generated file/chunk progress,
repair round numbers, and verification status. CLI shutdown closes the shared
runtime; applications embedding the client should call `CopilotSDKClient.shutdown()`
when finished (also registered for normal process exit).

Dependencies resolve from public PyPI so local development and CI do not require
access to an environment-specific package mirror. Keep any local mirror
configuration and credentials out of committed dependency files.

`DEFAULT_MODEL` and API credentials can be inherited from the process environment;
a repository `.env` file is optional and does not override inherited values.
CLI diagnostics go to stderr with a timezone-qualified timestamp, severity,
logger name, and source file/line. Generation and syntax-repair failures also
include exception tracebacks, including failures in individual code chunks.

### Evidence-grounded issue planning and NFR discovery

Issue experiments discover relevant NFRs from the issue's behavioral evidence;
they do not require NFR labels in the issue or a preset list in the run input.
Pilot 2 no longer supplies an NFR focus. The first planning request extracts an
attributed summary, requirements, acceptance checks, conflicts and relevant
canonical NFR IDs from the existing KB taxonomy. Unknown citations or NFR IDs
block generation rather than substituting default NFRs.

The existing NFR relationship expansion and KB endorsement/RAG remain in place.
A second request combines that knowledge with baseline declarations to assign
requirements to existing symbols or explicitly owned new declarations, including
baseline ranges, dependencies and validation checks. Both planning results are
reused across generation files/chunks. Citation checks establish provenance, not
proof that a model's interpretation is correct; compilation and tests still matter.
An invalid implementation plan gets at most one corrective request with its
validation error; a second invalid response blocks generation. NFR discovery is
not rerun, and this correction never relaxes ownership or evidence checks.

Discussion collection paginates up to `--max-issue-comments` (default 200), then
selects bounded relevant evidence, including useful later comments. Attribution,
complete selected fenced code blocks, omissions and a fingerprint are retained.
The selected body budget is `--max-issue-evidence-chars` (default 20000).
`--issue-context-cutoff` optionally excludes later or undated comments; it must
include a timezone. An issue body edited after the cutoff is rejected because
the current API response cannot reconstruct its historical contents. Without a
cutoff, reports explicitly warn that discussion may include post-fix information.
Reference implementation source/diffs are not supplied to this planner.

Grounded plans reject duplicate symbol owners, existing-symbol creation,
ungrounded targets, invalid ranges, missing requirements and cyclic dependencies.
Source hashes reject stale baseline inputs. Unassigned files are preserved
without a model request; chunked generation requests only assigned chunks, and
new declarations have one insertion anchor. Dependencies express shared planning
contracts and are validated, but generation does not execute or verify each plan
step separately. JSON and Markdown reports retain the discovery evidence and plan.
`--nfr-focus` remains an explicit, reported manual override, not an experiment
default. Legacy non-issue planning callers retain their existing defaults.

### LLM-controlled repair

Repair decisions, diagnoses, edit transactions, and checkpoint selection belong
to the LLM. Deterministic services provide literal source, AST headers and
positions, compiler/test output, search results, hashes, and isolated execution.
They do not infer repair owners, prescribe fixes, rank diagnostic codes, or prune
branches based on error counts. Utility prompts live in `templates/utils`.

Two scheduling modes share the same model-controlled action protocol:

- **loop**: the model chooses the next error or hypothesis, source investigation,
  coherent multi-file edit, verification, restoration, and stop/finish action.
- **tree**: the model can request alternative goals with explicit edit budgets.
  Sibling loops run concurrently in isolated source snapshots. All provisional
  checkpoints and observations return to the parent model, which chooses whether
  to resume, fork again, stop, or finish. The scheduler never chooses a winner.
  Child loops cannot recursively fork; the parent can resume a child and fork
  again to build deeper trees.

Configure resource scheduling under `execution`:

```yaml
execution:
  repair_mode: tree
  repair_concurrency: 3
  max_build_repair_attempts: 10
  repair_agent_max_seconds: 1800
```

`max_build_repair_attempts` is the shared edit-transaction budget for both build
and test repair, across all branches. Actions are also bounded (eight per edit,
shared by parent and children). Time is checked between actions; an in-flight
model call or verification may complete after that scheduling deadline.
Concurrency caps resource use, not semantic branch selection.

The model can read/search/inspect sources, edit multiple files atomically,
verify, restore any retained snapshot, finish, or stop. Source paths and hashes
are checked mechanically. Each proposed transaction receives an LLM semantic
review against the requirements and verification contract; there is no
filename-based fix policy. Initial localization does not restrict legitimate
additional production files or helpers.
Generated test fixtures can also be corrected without weakening assertions,
exercised cases, coverage or production contracts. Baseline tests and independent
acceptance remain protected, including baseline checks in files that also contain
generated tests. The model and transaction reviewer receive pinned baseline
source and initial-generated provenance; `read_source` can select `current`,
`baseline` or `initial_generated` versions. If provenance is unavailable, the
model must not assume a test was generated.

Changes remain provisional until the model selects a fully verified snapshot.
Promotion requires a real passing build and full tests, consistent positive test
totals, no new skips, no reduced suite, and no timeout. The largest observed suite
across sibling branches remains the promotion floor. Passing tests alone do not
prove requirement fidelity: the model must also explain its requirements review,
and independent behavioral acceptance tests remain necessary.

The issue runner accepts `--repair-mode loop|tree`, `--repair-concurrency`, and
`--repair-agent-max-seconds` overrides. Obsolete scoped-patch and compiler-routing
strategies are removed rather than retained as alternate semantic policies.
Invalid or obsolete execution settings now fail explicitly instead of silently
reverting to defaults.
Schema-invalid utility responses receive one bounded LLM correction request.
Validation stays strict; repeated invalid responses or provider failures remain
explicit errors, without heuristic coercion or approval fallbacks.

## Frozen repair replay

Saved candidates are optional debugging/reproducibility inputs, not a production
prerequisite. Replay uses the same LLM-controlled loop/tree engine and full
isolated verification:

```powershell
python -m src.main repair-replay --report reports/candidate.json --out-json reports/replay.json --max-attempts 10 --repair-mode tree --repair-concurrency 3 --repair-agent-max-seconds 1800
```

`--max-attempts 0` performs verification only. Compile-only replay is explicit and
uses `--no-run-tests`; it must not be reported as full behavioral acceptance.
Candidate resumption validates
source-report provenance, canonical paths, complete inputs, and selected snapshot
fingerprints. Reports retain model actions, semantic reviews, branch audits,
source snapshots, and actual verification observations. A failed or exhausted
repair retains the original input instead of promoting an unverified candidate.

## LocalAI: run a local LLM server and connect the project

This project supports LocalAI as an LLM provider. The LocalAI server runs locally (default HTTP port 8080) and the project will use the `API_KEY` from the project's `.env` file when present.

Visit http://localhost:9090 to check localai WEB UI

### Quick Start with Docker Compose

Use the provided script to set up models and start the LocalAI server with Docker Compose:

Windows (PowerShell):
```pwsh
.\setup\start_docker_localai.ps1
```

Unix-like systems (bash):
```bash
./setup/start_docker_localai.sh
```

The script will:
1. Create a `models/` directory in the repository root
2. Try to clone the default CodeGen model (`Salesforce/codegen-350M-mono`) from Hugging Face
3. Generate an `API_KEY` in `.env` if one doesn't exist
4. Start the Docker Compose stack

### Manual Setup (without scripts)

1. Generate an API key and create `.env`:
```shell
# Using Python
echo "API_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(16))')" > .env

# Or using openssl
echo "API_KEY=$(openssl rand -hex 16)" > .env
```

2. Start a LocalAI server (basic Docker example):
```bash
# From repo root, build or pull LocalAI image and run
docker run -p 8080:8080 ghcr.io/go-skynet/localai:latest --http-port 8080
```

For full setup and model installation, refer to the LocalAI docs:
- Getting started: https://localai.io/basics/getting_started/
- Models guide: https://localai.io/docs/getting-started/models/

Authentication note: If you want to enable authentication on the LocalAI server, follow LocalAI docs to pass the auth token/flags to the container and use the same token in `.env` (the client will send `Authorization: Bearer <API_KEY>`).

3. available_models.yaml includes a "localai" entry that points to http://localhost:8080. The local client will use that endpoint automatically.

Docker Compose (local development)
----------------------------------

This repository includes a `docker-compose.yml` (project root) and a top-level `Dockerfile` to run the Python app together with a LocalAI container. The LocalAI Dockerfile lives in `docker/localai/Dockerfile` and exposes the default HTTP port 8080.

Notes and recommended workflow:

- The app service uses an environment variable `LOCALAI_ENDPOINT` set to `http://localai:8080` by default so the app can reach the LocalAI service by service name on the Docker network.
- If you want to supply an API key for LocalAI authentication, put it in a `.env` file as `API_KEY=<your-token>` and the Python client will send it as `Authorization: Bearer <API_KEY>`.
- If you plan to provide model binaries to LocalAI, create a `models/` directory in the repo root and it will be mounted into the LocalAI container (`./models:/models`).

Quick commands (from repo root):

```powershell
# Build images and start services
docker-compose up --build

# Run in background
docker-compose up -d --build

# Stop and remove containers
docker-compose down
```

Named volume alternative:

```powershell
# Start LocalAI with a named Docker volume for /models
docker compose -f docker-compose.localai-volume.yml up -d --build

# Stop and remove container (keeps named volume data)
docker compose -f docker-compose.localai-volume.yml down
```

The app container runs `python src/main.py` by default. You can still run the code locally in a virtualenv â€” the docker setup is optional and intended for local integration testing with LocalAI.

If you prefer to run LocalAI manually (no docker-compose), you can still follow the previous LocalAI `docker run` example above and point the app to the endpoint using `LOCALAI_ENDPOINT=http://localhost:8080` or by updating `available_models.yaml`.

## Usage

1. Run `python src/main.py`
2. Enter the path to the target code file
3. Enter the path to the migration prompt file

## MCP server for SWE / NFR context

This repo also provides an MCP server that exposes software-engineering knowledge bases
for clean code and NFR-aware code generation.

- Server entry point: `src/mcp/swe_mcp_server.py`
- knowledge base sources: `knowledge bases/ground_data` and `knowledge bases/linked_data`

### Running the MCP server

From the project root, after installing dependencies via the setup script or Poetry:

```bash
python -m src.main mcp-server
```

This starts a FastMCP server on stdio that can be registered with any MCPâ€‘aware
client (e.g., via `mcp dev` / `mcp install`).

### Available tools

- `plan_swe_code_change(problem_description, target_language=None, nfr_focus=None)`
	- Stage 1 â€“ planning. Returns a structured `CodeGenPlan` and **must be
		called first** to create a highâ€‘level plan for the code change, guided
		by the SWE knowledge base.
- `build_swe_code_context(plan, include_templates=True, security_extra_context=None, prompt_output_folder=None, write_executed_prompts=False)`
	- Stage 2a â€“ context building. Takes a `CodeGenPlan` and returns a
		`SweContext` containing:
		- A text summary (`swe_summary`) built from the SWE knowledge bases
		- Optional concern assets loaded from:
			- `templates/data/<swe_concern>/*.md`
			- `knowledge/data/<swe_concern>/<concern_group>/data.json`
		- Optional persisted prompt artifacts when `prompt_output_folder` is set
		- Optional `executed_prompts.md` with timestamp-ordered rendered prompts when `write_executed_prompts=True`
			(useful for auditing/debugging generated prompt bundles)
- `judge_swe_code_change(swe_context, original_code, modified_code)`
	- Stage 2b â€“ explainable code changes. Uses the SWE knowledge base plus the
		Stage 1 plan/context to return a structured `SweCodeChangeExplanation`
		(overall verdict, rationale, perâ€‘NFR impacts, risks, and recommended
		tests) comparing original vs. modified code.

The intended agentic flow is:

1. Call `plan_swe_code_change` to show the user a knowledge-base-guided plan.
2. Once approved, call `build_swe_code_context` and inject the returned
	`swe_summary` and templates into your LLM prompts for code generation.
3. After applying the changes in your own agent or tool, call
	`judge_swe_code_change` with the original and modified code to obtain an
	explainable assessment of the change.

Architecture diagrams for this execution flow (data flow, component integration,
and sequence view) are documented in:

- [docs/architecture/agent-execution-data-flow.md](docs/architecture/agent-execution-data-flow.md)
## Linting

The project uses [ruff](https://docs.astral.sh/ruff/) (replaces `flake8` + `black`) and a custom import consistency script.
Run from the repo root after activating your virtual environment.

**ruff** â€“ lint (style, errors, import order):
```shell
ruff check src tests
```

**ruff** â€“ format check (equivalent to `black --check`):
```shell
ruff format --check src tests
```

Exit code is non-zero when violations are found, so both commands are suitable for CI gates.

## Testing and Coverage

Run the full test suite locally:

```shell
pytest
```

The project enforces a minimum of 80% coverage via `pytest.ini` (`--cov-fail-under=80`).

## CI

GitHub Actions workflow: `.github/workflows/ci.yml`

- Runs on push to `master` and on pull requests
- Installs dependencies with Poetry
- Runs `pytest` with coverage gate
- Uploads `coverage.xml` as a build artifact

## CD

GitHub Actions workflow: `.github/workflows/cd.yml`

- Runs on push to `master`
- Builds Docker image from the repository Dockerfile
- Pushes image to GitHub Container Registry as `ghcr.io/<owner>/<repo>`

## Structure
- `src/main.py`: Entry point
- src/service/: Business logic and services
- src/mcp/: MCP server implementation
- `src/utils/`: Utility functions
- `src/llm_client/localai_client.py`: LocalAI HTTP client wrapper
- `available_models.yaml`: Model/provider configuration (add LocalAI)

## Features

This tool reads a target code file and migration prompts, then explains:
- **Why** migration is needed
- **How** migration should be performed
- **Unsafe changes** that may occur

Note: For specific LocalAI model selection and model files, consult https://localai.io/basics/getting_started/. The LocalAI container may require additional flags to load model binaries and/or enable authentication.
