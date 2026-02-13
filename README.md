# 🍝 Spaghetti Code Rescue Tools

A comprehensive toolkit for analyzing and rescuing messy, complex, and hard-to-maintain code. This tool helps identify code smells, complexity issues, and architectural problems in Python projects.

## 🌟 Features

- **Complexity Analysis**: Calculate cyclomatic complexity, identify long functions, and measure nesting depth
- **Dependency Analysis**: Extract and analyze imports, find unused dependencies
- **Code Smell Detection**: Identify anti-patterns like long methods, large classes, too many parameters, and deep nesting
- **Project-Wide Analysis**: Analyze entire Python projects at once
- **Multiple Output Formats**: Human-readable text or JSON for integration with other tools

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/HanzoRazer/code-rescue-tool.git
cd code-rescue-tool

# Install dependencies
pip install -r requirements.txt

# Install the tool
pip install -e .
```

## 📖 Usage

### Basic Commands

#### Analyze Complexity
```bash
code-rescue complexity path/to/file.py
```

Analyzes code complexity metrics including:
- Lines of code (LOC, SLOC, LLOC)
- Cyclomatic complexity for each function
- Long functions (>50 lines)
- Maximum nesting depth

#### Analyze Dependencies
```bash
code-rescue dependencies path/to/file.py
```

Examines code dependencies:
- All imports (standard library, third-party, local)
- Import counts and summary
- Potentially unused imports

#### Detect Code Smells
```bash
code-rescue smells path/to/file.py
```

Identifies common code smells:
- Long methods (>50 lines)
- Large classes (>200 lines)
- Functions with too many parameters (>5)
- Deeply nested code (>4 levels)
- Duplicate code patterns

#### Complete Analysis
```bash
code-rescue analyze path/to/file.py
```

Runs all analysis tools on a single file for a comprehensive report.

#### Project-Wide Analysis
```bash
code-rescue project path/to/project/
```

Analyzes all Python files in a project directory.

### Output Formats

All commands support both text and JSON output:

```bash
# Human-readable text output (default)
code-rescue complexity file.py

# JSON output for integration with other tools
code-rescue complexity file.py --format json
```

## 📊 Example Output

```
📊 Complexity Analysis: example.py

============================================================

📈 Code Metrics:
  Lines of Code (LOC): 150
  Logical LOC: 95
  Source LOC: 120
  Comments: 15
  Blank lines: 30

🔄 Cyclomatic Complexity:
  🟢 simple_function (line 5): 2
  🟡 moderate_function (line 15): 8
  🔴 complex_function (line 40): 15

📏 Long Functions (>50 lines):
  ⚠️  process_data (line 60): 75 lines

🪆 Nesting Depth:
  ⚠️  nested_logic (line 100): depth 6
```

## 🛠️ Use Cases

- **Code Reviews**: Identify problematic areas before merging
- **Refactoring**: Find high-priority targets for improvement
- **Technical Debt**: Track complexity over time
- **Onboarding**: Help new developers understand code structure
- **CI/CD Integration**: Fail builds that exceed complexity thresholds

## 📝 Example: Analyzing Bad Code

See the `examples/` directory for sample spaghetti code and analysis results.

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest new features
- Submit pull requests

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built with:
- [Radon](https://radon.readthedocs.io/) - Python code metrics
- [Click](https://click.palletsprojects.com/) - CLI framework

## 🔮 Future Enhancements

- Support for more programming languages
- Integration with popular IDEs
- Automated refactoring suggestions
- Complexity trend tracking over time
- CI/CD plugins for popular platforms
