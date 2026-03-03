# Critical Design Review: Skylos v3.4.2

**Reviewer:** GitHub Copilot  
**Date:** February 24, 2026  
**Subject:** [Skylos](https://github.com/oha/skylos) — Privacy-First SAST, Dead Code Detection & Security Auditor  
**Scope:** Full codebase (`skylos-main/`), including CLI, analysis engine, rule system, LLM subsystem, CI/CD integration, MCP server, VS Code extension, TUI, Docker, pre-commit hooks, and test suite  

---

## Table of Contents

- [Stated Assumptions](#stated-assumptions)
- [1. Purpose Clarity — 8/10](#1-purpose-clarity--810)
- [2. User Fit — 7/10](#2-user-fit--710)
- [3. Usability — 7/10](#3-usability--710)
- [4. Reliability — 6/10](#4-reliability--610)
- [5. Manufacturability / Maintainability — 5/10](#5-manufacturability--maintainability--510)
- [6. Cost of Adoption & Operation — 7/10](#6-cost-of-adoption--operation--710)
- [7. Safety — 7/10](#7-safety--710)
- [8. Scalability — 6/10](#8-scalability--610)
- [9. Aesthetics — 8/10](#9-aesthetics--810)
- [Summary Scorecard](#summary-scorecard)
- [Top 5 Priorities](#top-5-priorities)
- [Appendix A: Project Inventory](#appendix-a-project-inventory)
- [Appendix B: Module-Level Code Quality Inspection](#appendix-b-module-level-code-quality-inspection)

---

## Stated Assumptions

1. **Target audience** is professional Python/TypeScript developers and DevOps engineers working on medium-to-large codebases who need dead code detection, security scanning, and quality gates in CI/CD.
2. **Competitive frame** is Vulture (dead code), Bandit (security), Ruff/Pylint (quality) — Skylos aims to unify all three with an LLM augmentation layer.
3. The project is assessed as a **solo/small-team open-source product** at Beta maturity (v3.4.2, Apache 2.0, PyPI-published).
4. "Manufacturability" is interpreted as **maintainability and contribution ease** for an open-source tool.
5. "Cost" is interpreted as **total cost of adoption, operation, and ownership**, not monetary price.
6. "Safety" is interpreted as **the tool's operational safety** (can it corrupt user code, leak secrets, cause CI failures by accident?) plus the security posture of the tool itself.
7. "Aesthetics" covers CLI output quality, documentation design, and the overall developer experience polish.
8. The 1,458-line README, 84 test files, and 30+ source modules serve as the primary evidence basis.

---

## 1. Purpose Clarity — 8/10

### Justification

The tagline *"Privacy-first SAST tool for Python, TypeScript, and Go"* is sharp and immediately differentiating. The README opens with a clear value proposition: hybrid AST + optional LLM analysis, multi-language dead code detection, security auditing, and quality scoring. The benchmark versus Vulture provides concrete proof of superiority:

| Metric | Skylos (c=20) | Vulture |
|--------|--------------|---------|
| Recall | **100%** | 82.8% |
| Precision | **76.3%** | 55.8% |

### What Holds It Back

The project tries to be **five tools at once** — dead code detector, security auditor, quality linter, LLM remediation agent, and CI/CD gatekeeper. While each is well-executed individually, the breadth muddles the elevator pitch. A new user landing on the README faces 1,458 lines of documentation before understanding the tool's boundaries. The distinction between `--danger`, `--quality`, `--secrets`, `--audit`, `--trace`, and `agent security-audit` vs `agent analyze` is confusing.

### Concrete Improvements

1. **Add a "What Skylos Is / What It Is Not" section** in the first 20 lines to distinguish it from Ruff, Bandit, Vulture, and Semgrep.
2. **Create a quick-decision matrix** (table: "I want X → run this command") as the second section, before installation.
3. **Split the README** into a concise `README.md` (< 300 lines) and a `docs/` folder with `USAGE.md`, `RULES.md`, `CI-CD.md`, `LLM.md`, `CONFIGURATION.md`.

---

## 2. User Fit — 7/10

### Justification

The primary persona (Python developer wanting dead-code and security scanning) is well-served. Framework detection for Flask, Django, FastAPI, pytest, and attrs means fewer false positives out of the box. The confidence scoring system (0–100) is genuinely novel and lets users tune aggressiveness via `-c`. TypeScript support extends reach to full-stack teams.

### What Holds It Back

- **Go support** is via an external binary with no in-tree implementation visible — it's a checkbox feature.
- **LLM features** require API keys or local model setup, creating a two-tier experience that is poorly communicated (which features need LLM? which don't?).
- The **VS Code extension, Streamlit app, MCP server, and pre-commit hooks** are scattered integration points that suggest the tool is spread across many secondary personas without deeply satisfying any single one.

### Concrete Improvements

1. **Create persona-based quick-starts:** "For a Python team", "For a TypeScript team", "For CI/CD engineers", "For LLM-augmented analysis".
2. **Mark Go support as "Experimental"** in all documentation and the CLI help text.
3. **Add a clear "LLM vs Static-Only" comparison** showing what you get without any API key.
4. **Remove the Streamlit web app from the main distribution.** It's a demo, not a product. Ship it as a separate repo or under `examples/`.

---

## 3. Usability — 7/10

### Justification

The zero-config `skylos .` entry point is excellent. Rich-powered output is readable and well-formatted. The `--json`, `--sarif`, `--tree`, `--table` output modes cover all integration scenarios. Interactive mode (`-i`) with inquirer is a nice touch. The TUI dashboard adds a visual dimension. Baseline tracking, inline pragmas, and whitelist configuration give users progressive control.

### What Holds It Back

The CLI has accumulated too many flags and subcommands:

- **Main command:** 20+ flags (`--json`, `--tree`, `--table`, `--sarif`, `-c`, `--comment-out`, `-o`, `-v`, `--version`, `-i`, `--dry-run`, `--exclude-folder`, `--include-folder`, `--secrets`, `--danger`, `--quality`, `--trace`, `--audit`, `--fix`, `--model`, `--gate`, `--force`)
- **Agent subcommands:** `analyze`, `security-audit`, `fix`, `review`, `remediate`
- **Other commands:** `baseline`, `cicd init/gate/annotate/review`, `init`, `key`, `whitelist`, `run`

There's no `--help` hierarchy visible in the README — a new user running `skylos --help` likely gets a wall of text. The configuration lives in `pyproject.toml` under `[tool.skylos]`, which is appropriate, but the relationship between CLI flags and config keys is undocumented.

### Concrete Improvements

1. **Implement command groups** using argparse subparsers more aggressively: `skylos scan`, `skylos fix`, `skylos gate`, `skylos config`. Keep `skylos .` as a shortcut for `skylos scan .`.
2. **Add `skylos doctor`** — a diagnostic command that reports: detected language, config loaded, LLM availability, baseline state, exclusion patterns active.
3. **Add a CLI reference page** in docs that maps every flag to its `pyproject.toml` equivalent.
4. **Cap `skylos --help` at 40 lines** with `skylos --help-all` for the full listing.

---

## 4. Reliability — 6/10

### Justification

84 test files is commendable coverage for an open-source SAST tool. Individual rule tests (SQL injection, XSS, CORS, JWT, etc.) use proper fixtures and assert specific rule IDs. The benchmark methodology is transparent and reproducible. The remediation agent has a safety-first design: dry-run default, test validation, auto-revert on failure, max-fixes cap. Baseline tracking prevents regression.

### What Holds It Back

Several structural reliability concerns exist:

| Issue | Risk |
|-------|------|
| `cli.py` at **3,526 lines** is an untestable monolith | A bug in billing logic could crash a scan |
| `penalties.py` is a **501-line single function** with ~40 early-return branches | Any framework penalty change risks cascading regressions |
| **Global mutable state** in `implicit_refs.pattern_tracker` (module singleton) | Thread-safety and test-isolation risks |
| `conftest.py` has a **no-op autouse fixture** (`cleanup_temp_files`) | Dead code in the test infrastructure itself |
| **No integration test** for the full CLI → report → gate → annotate pipeline | The 3,526-line `cli.py` has limited coverage |
| **Duplicate `non_import_defs` variable** re-declared twice in `analyzer.py`'s `_mark_refs` | Latent bug |

### Concrete Improvements

1. **Split `cli.py`** into: `cli_args.py` (parsing), `cli_output.py` (formatting), `cli_deploy.py` (deployment wizard), `cli_upload.py` (API interactions), `cli_main.py` (orchestration). Target < 500 lines each.
2. **Refactor `penalties.py`** into a data-driven registry: each framework penalty is a declarative config (methods set, bases set, confidence result) processed by a 20-line generic loop.
3. **Add a full end-to-end CLI test** that runs `skylos . --json --danger --quality` on `app.py` (the demo target) and asserts expected output structure, exit code, and minimum finding counts.
4. **Replace the `pattern_tracker` singleton** with dependency injection — pass it as a parameter to `Skylos.__init__`.
5. **Fix the duplicate `non_import_defs` variable.**

---

## 5. Manufacturability / Maintainability — 5/10

### Justification

Some modules are exemplary:

| Module | Lines | Quality |
|--------|-------|---------|
| `tracer.py` | 212 | Perfect SRP, thread-safe context manager |
| `llm/orchestrator.py` | 278 | Clean 5-step pipeline with proper delegation |
| `architecture.py` | 502 | Well-structured dataclasses, clear metrics |
| `linter.py` | 20 | Elegant visitor dispatch pattern |
| `rules/danger/` | ~12 submodules | Excellent per-vulnerability decomposition |

The CHANGELOG is detailed and well-maintained (759 lines across many releases).

### What Holds It Back

This is the project's **weakest area.**

#### The Big Three

3 files account for **7,122 lines (~57% of estimated total source):**

```
cli.py       3,526 lines  ← God module
visitor.py   1,958 lines  ← Monolithic AST visitor
analyzer.py  1,638 lines  ← Mixed Python + TS analysis
```

These are maintenance bottlenecks — any contributor modifying the CLI risks merge conflicts with any other CLI change.

#### Thin Base Class

`rules/base.py` is only **25 lines** — too thin to serve as a framework:
- No `severity` property
- No `category` property
- No `enabled` flag
- No auto-registration mechanism
- Rules return raw `dict` objects instead of typed diagnostics
- Adding a new rule requires manual wiring

#### Pervasive Duplication

| Duplicated Pattern | Locations |
|-------------------|-----------|
| `_shorten_path` helper | `cli.py` and `tui.py` |
| `generic_visit` with child iteration | `visitor.py` and `danger.py` |
| Django/DRF penalty blocks | 7× copy-paste in `penalties.py` |
| ABC/Protocol detection logic | `penalties.py`, `visitor.py`, `architecture.py` |
| Codemod read→transform→write wrappers | 4× copy-paste in `cli.py` (lines 90–163) |

#### Contributor Experience

- `CONTRIBUTING.md` is **47 lines** with no architecture overview, no module map, no "where to add a new rule" guide.
- No type checking infrastructure: no `py.typed` marker, no `mypy.ini`, no type-check CI step.
- Type hints are used inconsistently across the codebase.

### Concrete Improvements

1. **Decompose the Big Three:**
   - `cli.py` → `cli_args.py`, `cli_output.py`, `cli_deploy.py`, `cli_upload.py`, `cli_main.py`
   - `visitor.py` → `visitor_base.py`, `import_visitor.py`, `def_visitor.py`, `ref_visitor.py`, `post_processor.py`
   - `analyzer.py` → `analyzer_core.py`, `ts_analyzer.py`, `heuristics_engine.py`
2. **Enrich `rules/base.py`:** Add `severity`, `category`, `description` abstract properties. Define a `Finding` dataclass for rule output. Add `__init_subclass__` auto-registration.
3. **Create `skylos/utils.py`:** Move `_shorten_path`, `generic_visit` base, ABC/Protocol detection helpers into a shared module.
4. **Add `ARCHITECTURE.md`:** Document the module dependency graph, data flow (`file → visitor → defs/refs → analyzer → findings → pipeline → output`), and "how to add a new rule" tutorial.
5. **Add `mypy --strict` to CI.** Start with `--follow-imports=skip` and progressively increase coverage.

---

## 6. Cost of Adoption & Operation — 7/10

### Justification

- **Installation:** single `pip install skylos` or `uv add skylos`
- **Zero configuration** required for basic scanning
- **12 core dependencies** — reasonable and well-chosen (Rich, libcst, tree-sitter, litellm, networkx)
- **Docker image:** 5-line Alpine build
- **GitHub Action:** provided as a composite action
- **Pre-commit hooks:** ready to copy
- **Incremental adoption:** start at `-c 90` (high-confidence only) and lower over time

### What Holds It Back

| Dependency | Problem |
|-----------|---------|
| `textual>=1.0.0` | Heavy; pulled for all users even if TUI never used |
| `litellm>=1.81.3` | 20+ transitive sub-dependencies; pulled for all users even if LLM never used |
| `keyring>=25.6.0` | System-level dependency that can fail in headless CI (no secret backend) |
| `pyperclip` | Requires clipboard access — fails in CI/Docker/SSH |

No `[project.optional-dependencies]` split for TUI or LLM features. Go support requires a pre-built binary that must be separately acquired — the installation path is undocumented.

### Concrete Improvements

1. **Move to optional extras:**
   - `skylos[tui]` → `textual`
   - `skylos[llm]` → `litellm`
   - `skylos[web]` → `flask`, `flask-cors` (already exists)
   - Core install: `rich`, `libcst`, `tree-sitter`, `tree-sitter-typescript`, `pyyaml`, `networkx`
2. **Replace `keyring`** with a simple encrypted file or environment variable for API key storage in CI. Use `keyring` only when available (`try`/`except` import).
3. **Add `--no-llm` and `--no-tui` guards** that produce clear error messages if the extras aren't installed, instead of `ImportError` tracebacks.
4. **Document Go binary acquisition** or remove Go from the feature list until it's pip-installable.

---

## 7. Safety — 7/10

### Justification

The remediation agent's safety design is **best-in-class** for this category:

- ✅ Dry-run by default
- ✅ Test validation before applying fixes
- ✅ Auto-revert on test failure
- ✅ Low-confidence findings skipped
- ✅ Max-fixes cap
- ✅ Changes on a new branch
- ✅ `--comment-out` mode (non-destructive alternative to `--fix`)
- ✅ Inline pragmas (`# skylos: ignore`) and baseline tracking prevent alert fatigue
- ✅ API keys stored via OS keyring, not plaintext
- ✅ Security disclosure policy exists (`SECURITY.md`)

### What Holds It Back

| Risk | Details |
|------|---------|
| **Vulnerable demo app in package root** | `app.py` (324 lines of deliberately vulnerable Flask code) ships at the repo root. If scanned during a real CI gate, it produces alarming findings that confuse results. |
| **Silent code corruption** | `codemods` can corrupt code if libcst's position tracking drifts after a prior codemod changes line numbers. The sequential apply model in `cli.py` doesn't re-parse between transformations. |
| **Tool uses patterns it warns against** | `os.system()` and `subprocess.run(shell=True)` appear in `gatekeeper.py`'s `run_cmd()`. While inputs are controlled, this is a bad optic and a supply-chain risk. |
| **MCP server auth undocumented** | `skylos_mcp/auth.py` exists but the README doesn't document required authentication setup. |

### Concrete Improvements

1. **Move `app.py`** to `test/fixtures/vulnerable_app.py` and update references.
2. **Re-parse between codemods:** After each libcst transformation, re-read the file and re-parse before applying the next to prevent position drift.
3. **Replace `subprocess.run(shell=True)`** in `gatekeeper.py` with `subprocess.run(cmd_list)` (list form). Replace `os.system()` calls with `subprocess.run()`.
4. **Document MCP authentication** requirements prominently. Add a warning if the server is started without auth configuration.
5. **Add a CLI warning** if `app.py` or any test fixture is included in a production gate scan.

---

## 8. Scalability — 6/10

### Justification

- `skylos/scale/parallel_static.py` provides **process-based parallelism** for file analysis.
- The pipeline supports **filtering findings to changed files only** (baseline diff).
- Tree-sitter integration for TypeScript means Python-AST-level performance for TS analysis.
- Architecture metrics module (coupling, cohesion, instability) can identify structural scaling problems in the *analyzed* codebase.

### What Holds It Back

| Bottleneck | Impact |
|-----------|--------|
| **No incremental analysis** | Every run re-parses all files. For a 10K-file monorepo, this means multi-minute scan times even when only 3 files changed. |
| **Double AST walk** in `visitor.py` | `generic_visit` override injects parent pointers on every node *before* the actual visit pass — O(2n) where n is tree size. |
| **4+ lookup passes** in `_mark_refs` | File-key, FQN, simple-name, dotted, same-file lookups — each is O(m) over all references. For 100K+ refs, this is O(4m × d). |
| **Sequential LLM calls** | Even with parallel static analysis, LLM analysis processes files sequentially with per-file API calls. |
| **No caching layer** | AST parse results, definition maps, and LLM responses are not cached between runs. |

### Concrete Improvements

1. **Implement file-level caching:** Hash file contents → cache parsed AST + defs/refs. On re-run, only re-analyze files whose hash changed. Store in `.skylos/cache/`.
2. **Add `--changed-only` flag** that integrates with `git diff HEAD~1` to analyze only modified files (beyond baseline filtering of *findings*).
3. **Batch LLM calls:** Send multiple files per LLM request (up to context window limits) instead of one call per file.
4. **Merge the two AST passes** in `visitor.py`: inject parent pointers during the same walk that collects defs/refs.
5. **Index defs by simple name** for O(1) lookup in `_mark_refs` instead of repeated linear scans.

---

## 9. Aesthetics — 8/10

### Justification

This is one of the project's strengths:

- **Rich-powered console output** with a custom theme (`good`/`warn`/`bad`/`muted`/`brand`) is visually polished.
- **Letter-grade system** (A+ through F) with category weights gives instant comprehension.
- **TUI dashboard** with Textual is genuinely impressive — tabbed views, DataTable navigation, severity charts, responsive layout.
- **Tree output mode** for dead-code hierarchies adds structural clarity.
- **SARIF export** follows the 2.1.0 spec correctly.
- **README** uses badges, quick-start blocks, and collapsible sections effectively.

### What Holds It Back

- **Inconsistent output pipeline.** `--table` uses Rich tables, `--tree` uses Rich trees, `--json` outputs raw JSON, `--sarif` outputs spec SARIF — but there's no unified "report" intermediate representation. Each mode builds its output from scratch.
- **Bare error messages.** When configuration is invalid or an API key is missing, the tool prints unformatted text rather than Rich-styled error panels.
- **Stale VS Code extension assets.** The extension uses a screenshot named `python-security-scan-vscode.png` — suggesting a rebrand that wasn't completed.

### Concrete Improvements

1. **Unify the output path:** Build a single `Report` dataclass from the analysis pipeline, then format it into Rich/JSON/SARIF/HTML in the output layer. This ensures all modes show consistent data.
2. **Style errors and warnings** with `rich.panel.Panel` + the custom theme. Add exit codes documentation visible in `--help`.
3. **Update VS Code extension assets** to use current branding. Rename the screenshot.
4. **Add `--color=auto|always|never`** to support piped output gracefully.

---

## Summary Scorecard

| # | Category | Score | Key Strength | Key Weakness |
|---|----------|-------|-------------|-------------|
| 1 | **Purpose Clarity** | 8/10 | Sharp tagline, benchmark proof | Scope creep (5 tools in one) |
| 2 | **User Fit** | 7/10 | Framework-aware confidence tuning | Go is vaporware, LLM tier unclear |
| 3 | **Usability** | 7/10 | Zero-config `skylos .` entry point | 20+ flags, no command hierarchy |
| 4 | **Reliability** | 6/10 | 84 test files, safe remediation agent | 3,526-line untestable CLI monolith |
| 5 | **Maintainability** | 5/10 | Excellent rule decomposition pattern | 57% of code in 3 god-files |
| 6 | **Cost** | 7/10 | Single `pip install`, incremental adoption | Heavy deps forced on all users |
| 7 | **Safety** | 7/10 | Dry-run default, auto-revert on failure | Vulnerable demo in package root |
| 8 | **Scalability** | 6/10 | Process-parallel static analysis | No caching, no incremental analysis |
| 9 | **Aesthetics** | 8/10 | Rich TUI, letter grades, SARIF export | No unified report intermediate form |
| | **Overall** | **6.8/10** | | |

---

## Top 5 Priorities

If I were the maintainer, these are the changes I'd make first, in order:

### Priority 1: Break Up `cli.py` (3,526 → 5 modules × ~500 lines)

**Impact:** Reliability ↑, Maintainability ↑, Testability ↑  
**Effort:** Medium (2–3 days)

Split into `cli_args.py` (parsing), `cli_output.py` (formatting), `cli_deploy.py` (deployment wizard), `cli_upload.py` (API interactions), `cli_main.py` (orchestration). This single change addresses three scoring categories simultaneously.

### Priority 2: Move `textual`, `litellm`, `keyring` to Optional Extras

**Impact:** Cost ↑, Usability ↑  
**Effort:** Low (half day)

Cuts install weight by ~70% for the 80% of users who just want `skylos . --json`. Add `skylos[tui]`, `skylos[llm]` extras to `pyproject.toml`.

### Priority 3: Enrich `rules/base.py` with Typed Output & Auto-Registration

**Impact:** Maintainability ↑, Scalability ↑  
**Effort:** Medium (1–2 days)

Add `severity`, `category`, `description` abstract properties. Define a `Finding` dataclass for rule output. Add `__init_subclass__` auto-registration (the pattern already used elsewhere in the codebase). This makes the rule system scalable and contributor-friendly.

### Priority 4: Add File-Content-Hash Caching

**Impact:** Scalability ↑, Usability ↑  
**Effort:** Medium (2 days)

Store parsed AST + defs/refs in `.skylos/cache/` keyed by file content hash. Turns a 60-second full scan into a 2-second incremental scan on unchanged code.

### Priority 5: Split the README (1,458 → ~300 + docs/)

**Impact:** Purpose Clarity ↑, Usability ↑  
**Effort:** Low (half day)

Move detailed sections into `docs/USAGE.md`, `docs/RULES.md`, `docs/CI-CD.md`, `docs/LLM.md`, `docs/CONFIGURATION.md`. Keep `README.md` as a concise landing page with links.

---

## Appendix A: Project Inventory

### Source Statistics

| Metric | Value |
|--------|-------|
| Version | 3.4.2 |
| License | Apache 2.0 |
| Python requirement | ≥ 3.10 |
| Core dependencies | 12 |
| CLI entry point | `skylos.cli:main` |
| Main CLI size | 3,526 lines |
| Analyzer size | 1,638 lines |
| Visitor size | 1,958 lines |
| API module size | 996 lines |
| Total source modules | 30+ files + 9 sub-packages |
| Test files | 84 |
| Security rules | 30+ (Python, TS, MCP) |
| Quality rules | 18+ |
| Languages supported | Python, TypeScript/TSX, Go (partial) |
| LLM providers | OpenAI, Anthropic, Ollama, LM Studio, vLLM (via litellm) |
| Output formats | Rich table, tree, JSON, SARIF, TUI |
| CI integrations | GitHub Actions, Jenkins, CircleCI, GitLab |
| Changelog | 759 lines across many versions |

### Package Structure

```
skylos/
├── __init__.py             (16 lines)
├── cli.py                  (3,526 lines)  ⚠ God module
├── analyzer.py             (1,638 lines)  ⚠ Mixed concerns
├── visitor.py              (1,958 lines)  ⚠ Monolithic visitor
├── api.py                  (996 lines)
├── config.py               (254 lines)    ✓ Clean
├── constants.py            (108 lines)    ✓ Clean
├── pipeline.py             (443 lines)    ✓ Good
├── grader.py               (308 lines)    ✓ Good
├── penalties.py            (501 lines)    ⚠ God function
├── fixer.py                (141 lines)    ✓ Clean
├── gatekeeper.py           (309 lines)    ✓ Good
├── sarif_exporter.py       (150 lines)    ✓ Clean
├── baseline.py             (89 lines)     ✓ Clean
├── linter.py               (20 lines)     ✓ Elegant
├── codemods.py             (328 lines)    ✓ Good
├── tracer.py               (212 lines)    ✓ Excellent
├── tui.py                  (697 lines)    ✓ Good
├── architecture.py         (502 lines)    ✓ Good
├── implicit_refs.py        (173 lines)    ⚑ Global singleton
├── control_flow.py
├── circular_deps.py
├── credentials.py
├── login.py
├── server.py
├── sync.py
├── ast_mask.py
├── known_patterns.py
├── module_reachability.py
├── pyproject_entrypoints.py
├── pytest_unused_fixtures.py
├── adapters/               (3 files)
├── commands/               (2 files)
├── engines/                (2 files — Go support)
├── llm/                    (15 files)     ✓ Well-decomposed
├── misc/                   (1 file)
├── rules/                  (20+ files)    ✓ Well-decomposed
├── scale/                  (2 files)
└── visitors/               (4 files)
```

### Integration Surface

| Integration | Implementation |
|-------------|---------------|
| GitHub Actions | `action.yml` (157 lines, composite) |
| Docker | `Dockerfile` (5 lines, Alpine) |
| Pre-commit | `.pre-commit-config.yaml` + `.pre-commit-hooks.yaml` |
| VS Code | `editors/vscode/` (full extension, published) |
| MCP Server | `skylos_mcp/` (4 files: server, auth, init, main) |
| Streamlit | `app.py` (324 lines — demo/test target) |

---

## Appendix B: Module-Level Code Quality Inspection

### Files Rated "Excellent" or "Good"

| Module | Lines | SRP | Notes |
|--------|-------|-----|-------|
| `tracer.py` | 212 | Excellent | Thread-safe context manager, configurable patterns |
| `llm/orchestrator.py` | 278 | Good | Clean 5-step pipeline: scan → plan → fix → test → PR |
| `architecture.py` | 502 | Good | Dataclasses, clear metrics, DIP violation detection |
| `linter.py` | 20 | Excellent | Elegant pluggable visitor dispatch |
| `rules/danger/danger.py` | 162 | Good | Aggregator pattern, proper delegation to submodules |
| `tui.py` | 697 | Good | Focused on Textual dashboard; minor duplication with `cli.py` |
| `config.py` | 254 | Good | Clean config loading, whitelist handling, inline ignore parsing |
| `baseline.py` | 89 | Good | Simple fingerprint-based baseline tracking |
| `gatekeeper.py` | 309 | Good | Clear gate check logic, markdown summary generation |

### Files Rated "Needs Improvement"

#### `cli.py` — 3,526 lines (SRP: Very Poor)

**Responsibilities mixed into one file:**
- Argument parsing (`argparse`)
- Logging setup (`Rich` handler)
- 4 codemod wrapper functions (lines 90–163) — near-identical read→transform→write with same try/except
- Path shortening utilities
- Project root detection
- Rich TUI output formatting
- Upload/billing logic
- Login orchestration
- CI detection
- Subprocess deployment execution
- Credit balance checking
- Interactive prompts

**Recommendation:** Split into 5 modules of ~500 lines each.

#### `visitor.py` — 1,958 lines (SRP: Moderate)

Singularly focused on AST visiting, but its size indicates it needs decomposition. The `generic_visit` override injects parent pointers on every node — a pervasive side effect that could be a single preprocessing pass. `finalize()` and `_apply_string_patterns` do post-processing separate from the visit concern.

**Recommendation:** Extract into base visitor + specialized sub-visitors (imports, defs, refs, post-processing).

#### `analyzer.py` — 1,638 lines (SRP: Moderate)

Core ref-marking responsibility is coherent, but TypeScript import resolution (`_resolve_ts_module`, `_build_ts_import_graph`, `_demote_unconsumed_ts_exports`) is interleaved with Python analysis. `_apply_heuristics` hard-codes rule-like logic instead of delegating to the rule system. `_mark_refs` has a duplicate `non_import_defs` variable declaration.

**Recommendation:** Extract `TypeScriptAnalyzer` and `HeuristicsEngine` into separate modules.

#### `penalties.py` — 501 lines (SRP: Poor Internal Cohesion)

The entire file is one function with ~40 early-return branches. Django/DRF blocks (lines 115–165) repeat 7 identical structures differing only in method/base sets. Variable member checks (dataclass, namedtuple, attrs, ORM, Pydantic) are each a separate block with the same structure.

**Recommendation:** Convert to a data-driven registry with declarative penalty configs processed by a generic loop.

#### `api.py` — 996 lines (SRP: Weak)

Mixes CI detection, credential management, and API communication. `_detect_ci()` and `_extract_pr_number()` both contain per-provider branching with near-identical patterns.

**Recommendation:** Split CI detection into a data-driven table, separate credential management from HTTP communication.

#### `rules/base.py` — 25 lines (Too Thin)

No `severity`, `category`, or `description` properties. No `enabled` flag, no `configure()` hook, no base helper methods. Rules return raw `dict` instead of typed `Finding` objects. No auto-registration mechanism.

**Recommendation:** Expand to ~80 lines with `Finding` dataclass, abstract properties, and `__init_subclass__` registration.

### Cross-Cutting Concerns

| Concern | Finding |
|---------|---------|
| **Monolith risk** | `cli.py` (3,526) and `penalties.py` (501 as one function) are worst offenders |
| **Duplication** | `_shorten_path` in `cli.py` + `tui.py`; codemods 4× copy-paste; Django/DRF 7× identical; `generic_visit` in `danger.py` |
| **Tight coupling** | `analyzer.py` has inline TS resolution; `penalties.py` reaches into `analyzer._global_*` internals via `getattr` |
| **Thin abstractions** | `rules/base.py` (25 lines) doesn't enforce consistency; rules return raw dicts |
| **Global state** | `implicit_refs.pattern_tracker` is a module singleton imported by both `visitor.py` and `analyzer.py` |
| **Test infrastructure** | `conftest.py` adequate but has no-op `cleanup_temp_files` fixture (dead code) |
| **Best-in-class** | `tracer.py`, `llm/orchestrator.py`, `architecture.py` — clean SRP, right-sized, well-decomposed |
