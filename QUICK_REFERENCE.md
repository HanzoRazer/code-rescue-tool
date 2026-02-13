# Quick Reference Guide for Code Rescue Tools

## Installation

```bash
pip install -r requirements.txt
pip install -e .
```

## Commands

### 1. Complexity Analysis
Analyzes code complexity metrics.

```bash
code-rescue complexity <file.py>
```

**What it detects:**
- Lines of code (LOC, LLOC, SLOC)
- Cyclomatic complexity per function
- Long functions (>50 lines)
- Deep nesting levels

**Color coding:**
- 🟢 Low complexity (≤5)
- 🟡 Medium complexity (6-10)
- 🔴 High complexity (>10)

### 2. Dependency Analysis
Examines imports and dependencies.

```bash
code-rescue dependencies <file.py>
```

**What it detects:**
- All imports (standard library, third-party, local)
- Import statistics
- Potentially unused imports

### 3. Code Smell Detection
Identifies common anti-patterns.

```bash
code-rescue smells <file.py>
```

**What it detects:**
- Long methods (>50 lines)
- Large classes (>200 lines)
- Functions with too many parameters (>5)
- Deep nesting (>4 levels)
- Duplicate code patterns

### 4. Complete Analysis
Runs all tools on a single file.

```bash
code-rescue analyze <file.py>
```

### 5. Project Analysis
Analyzes all Python files in a directory.

```bash
code-rescue project <directory/>
```

## Output Formats

All commands support both text and JSON:

```bash
# Human-readable text (default)
code-rescue complexity file.py

# JSON for tool integration
code-rescue complexity file.py --format json
```

## Thresholds

You can customize thresholds by editing the source code:

- **Long functions:** Default 50 lines
- **Large classes:** Default 200 lines
- **Too many parameters:** Default 5 parameters
- **Deep nesting:** Default 4 levels
- **High complexity:** Default 10

## Interpretation Guide

### Cyclomatic Complexity
- **1-5:** Simple, easy to test
- **6-10:** Moderate complexity, consider refactoring
- **11+:** High complexity, refactoring recommended

### Nesting Depth
- **1-3:** Acceptable
- **4:** Consider refactoring
- **5+:** Strongly recommend refactoring

### Function Length
- **<20 lines:** Good
- **20-50 lines:** Acceptable
- **50+ lines:** Consider breaking into smaller functions

## Examples

See `examples/spaghetti_code.py` for a sample file with various code smells.

```bash
# Analyze the example
code-rescue analyze examples/spaghetti_code.py
```

## Integration with CI/CD

Use JSON output in your CI/CD pipeline:

```bash
#!/bin/bash
# Example CI script
code-rescue complexity src/main.py --format json > complexity.json

# Parse and fail if complexity is too high
max_complexity=$(jq '[.cyclomatic_complexity[].complexity] | max' complexity.json)
if [ "$max_complexity" -gt 10 ]; then
  echo "❌ Code complexity too high: $max_complexity"
  exit 1
fi
```

## Tips for Rescuing Spaghetti Code

1. **Start with high-complexity functions** - Focus on functions with complexity >10
2. **Break down long functions** - Split functions >50 lines into smaller units
3. **Reduce nesting** - Use early returns and extract conditions
4. **Limit parameters** - Use data classes or configuration objects
5. **Remove unused imports** - Clean up to improve readability
6. **Test incrementally** - Add tests before refactoring

## Getting Help

```bash
code-rescue --help
code-rescue complexity --help
```
