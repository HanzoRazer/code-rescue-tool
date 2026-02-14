# code-rescue-tool

Spaghetti Code Rescue Tools - automated fixes for [code-analysis-tool](https://github.com/HanzoRazer/code-analysis-tool) findings.

## Overview

`code-rescue-tool` consumes analysis results from `code-analysis-tool` and generates rescue plans with automated or semi-automated fixes for common code issues.

```
┌─────────────────────────┐         ┌─────────────────────────┐
│   code-analysis-tool    │         │    code-rescue-tool     │
│                         │         │                         │
│  Analyzers → Findings   │────────▶│  Rescue Actions         │
│  Findings → Signals     │  JSON   │  (fix/refactor/remove)  │
│  (run_result_v1)        │         │                         │
└─────────────────────────┘         └─────────────────────────┘
```

## Installation

```bash
pip install -e .

# With code-analysis-tool integration
pip install -e ".[analysis]"

# With dev dependencies
pip install -e ".[dev]"
```

## Usage

### Generate a Rescue Plan

```bash
# From file
code-rescue plan ./analysis_result.json -o rescue_plan.json

# From stdin (pipe from code-analysis-tool)
code-audit scan ./my-project --output json | code-rescue plan -

# Dry run (preview)
code-rescue plan ./analysis_result.json --dry-run
```

### Apply Fixes (coming soon)

```bash
code-rescue fix ./rescue_plan.json --dry-run
code-rescue fix ./rescue_plan.json --apply --backup
```

## Supported Rules

| Rule ID | Action | Safety | Description |
|---------|--------|--------|-------------|
| `DC_UNREACHABLE_001` | Remove | Safe | Unreachable code after return/raise/break |
| `DC_IF_FALSE_001` | Remove | Safe | `if False:` blocks |
| `DC_ASSERT_FALSE_001` | Flag | Manual | `assert False` statements |
| `GST_MUTABLE_DEFAULT_001` | Replace | Safe | Mutable default arguments |
| `GST_MUTABLE_MODULE_001` | Flag | Manual | Module-level mutables |
| `GST_GLOBAL_KEYWORD_001` | Refactor | Manual | Global keyword usage |
| `SEC_HARDCODED_SECRET_001` | Extract | Semi-auto | Hardcoded secrets |
| `SEC_EVAL_001` | Replace | Manual | eval() usage |
| `SEC_SUBPROCESS_SHELL_001` | Replace | Semi-auto | shell=True in subprocess |
| `SEC_SQL_INJECTION_001` | Replace | Semi-auto | SQL injection risks |
| `SEC_PICKLE_LOAD_001` | Flag | Manual | pickle.load() usage |
| `SEC_YAML_UNSAFE_001` | Replace | Safe | Unsafe YAML loading |

## Schema Compatibility

- Consumes: `run_result_v1` from code-analysis-tool
- Produces: `rescue_plan_v1`

## Contract Parity with code-analysis-tool

`code-rescue-tool` vendors the upstream contract schema:

```
contracts/run_result.schema.json
```

This file **must remain byte-identical** to the version in:

```
https://github.com/HanzoRazer/code-analysis-tool
```

CI enforces this automatically via `ci/check_upstream_contracts.py`.

If CI fails with a contract mismatch:

### Sync manually

```bash
UPSTREAM_REF=main ./scripts/sync_contracts.sh
```

Or pin to a release tag:

```bash
UPSTREAM_REF=v1.0.0 ./scripts/sync_contracts.sh
```

Commit the updated schema and push.

## Development

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=code_rescue
```

## License

MIT
