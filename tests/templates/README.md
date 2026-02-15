# Reusable Test Patterns

Template test files copied from `code-analysis-tool`. Adapt these patterns for your own project.

## Templates

| File | Pattern | Use Case |
|------|---------|----------|
| `template_registry_contract.py` | Plugin Registry | Extensible systems with discoverable components |
| `template_golden_fixtures.py` | Golden Output | Deterministic transformations, regression tests |
| `template_exit_code_contract.py` | Exit Codes | CLI tools with defined exit semantics |
| `template_schema_validation.py` | Schema Validation | JSON schema contracts, positive + negative cases |
| `template_cli_api_parity_scan.py` | CLI/API Parity | Tools with both CLI and programmatic API |
| `template_cli_api_parity_debt.py` | CLI/API Parity | Debt snapshot/compare parity example |

## How to Use

1. Copy the template to your `tests/` directory
2. Rename to match your domain (e.g., `test_handler_registry_contract.py`)
3. Replace imports and class names with your project's equivalents
4. Update fixture paths and expected values

## Pattern Details

### Registry Contract
- Auto-discovers all implementations via `pkgutil.iter_modules`
- Verifies registered list is complete and exact (no missing, no extra)
- Good for: plugin systems, strategy patterns, handler registries

### Golden Fixtures
- Runs pipeline with deterministic inputs
- Normalizes volatile fields (timestamps, IDs, paths)
- Auto-generates expected output on first run
- Validates against schema on every run

### Exit Code Contract
- Documents exit code semantics as executable tests
- Tests both success paths (exit 0) and failure paths (exit 1, 2)
- Subprocess-based for true CLI testing

### Schema Validation
- Positive tests: example files validate against schema
- Negative tests: invalid payloads are rejected
- Tests invariants: enums, ranges, required fields

### CLI/API Parity
- Proves CLI and API produce byte-identical output
- Uses `--ci` mode for deterministic comparisons
- Catches divergence in compute paths
