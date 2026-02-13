"""Command-line interface for Code Rescue Tools."""

import click
import json
import os
from code_rescue.complexity import ComplexityAnalyzer
from code_rescue.dependencies import DependencyAnalyzer, ProjectDependencyAnalyzer
from code_rescue.smells import CodeSmellDetector

# Default thresholds for analysis
DEFAULT_LONG_FUNCTION_THRESHOLD = 50
DEFAULT_LARGE_CLASS_THRESHOLD = 200
DEFAULT_MANY_PARAMS_THRESHOLD = 5
DEFAULT_DEEP_NESTING_THRESHOLD = 4


@click.group()
@click.version_option(version='0.1.0')
def main():
    """Spaghetti Code Rescue Tools - Analyze and improve code quality."""
    pass


@main.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help='Output format')
def complexity(file_path, format):
    """Analyze code complexity metrics."""
    try:
        analyzer = ComplexityAnalyzer(file_path)
        report = analyzer.get_full_report()
        
        if format == 'json':
            click.echo(json.dumps(report, indent=2))
        else:
            _print_complexity_report(report)
    except Exception as e:
        click.echo(f"Error analyzing file: {e}", err=True)


def _print_complexity_report(report):
    """Print complexity report in human-readable format."""
    click.echo(f"\n📊 Complexity Analysis: {report['file']}\n")
    click.echo("=" * 60)
    
    # Raw metrics
    metrics = report['raw_metrics']
    if 'error' not in metrics:
        click.echo("\n📈 Code Metrics:")
        click.echo(f"  Lines of Code (LOC): {metrics['loc']}")
        click.echo(f"  Logical LOC: {metrics['lloc']}")
        click.echo(f"  Source LOC: {metrics['sloc']}")
        click.echo(f"  Comments: {metrics['comments']}")
        click.echo(f"  Blank lines: {metrics['blank']}")
    
    # Cyclomatic complexity
    cc = report['cyclomatic_complexity']
    if cc and 'error' not in cc[0]:
        click.echo("\n🔄 Cyclomatic Complexity:")
        for item in cc:
            symbol = "🟢" if item['complexity'] <= 5 else "🟡" if item['complexity'] <= 10 else "🔴"
            click.echo(f"  {symbol} {item['name']} (line {item['line']}): {item['complexity']}")
    
    # Long functions
    long_funcs = report['long_functions']
    if long_funcs and 'error' not in long_funcs[0]:
        click.echo(f"\n📏 Long Functions (>{DEFAULT_LONG_FUNCTION_THRESHOLD} lines):")
        for func in long_funcs:
            click.echo(f"  ⚠️  {func['name']} (line {func['line']}): {func['length']} lines")
    
    # Nesting depth
    nesting = report['nesting_depth']
    if nesting and 'error' not in nesting[0]:
        click.echo("\n🪆 Nesting Depth:")
        for item in nesting:
            if item['max_nesting'] > 3:
                click.echo(f"  ⚠️  {item['name']} (line {item['line']}): depth {item['max_nesting']}")


@main.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help='Output format')
def dependencies(file_path, format):
    """Analyze code dependencies."""
    try:
        analyzer = DependencyAnalyzer(file_path)
        imports = analyzer.extract_imports()
        counts = analyzer.count_dependencies()
        unused = analyzer.find_unused_imports()
        
        result = {
            'file': file_path,
            'imports': imports,
            'counts': counts,
            'unused': unused,
        }
        
        if format == 'json':
            click.echo(json.dumps(result, indent=2))
        else:
            _print_dependency_report(result)
    except Exception as e:
        click.echo(f"Error analyzing dependencies: {e}", err=True)


def _print_dependency_report(report):
    """Print dependency report in human-readable format."""
    click.echo(f"\n📦 Dependency Analysis: {report['file']}\n")
    click.echo("=" * 60)
    
    counts = report['counts']
    if 'error' not in counts:
        click.echo("\n📊 Import Summary:")
        click.echo(f"  Total imports: {counts['total']}")
        click.echo(f"  Standard library: {counts['standard']}")
        click.echo(f"  Third-party: {counts['third_party']}")
        click.echo(f"  Local: {counts['local']}")
    
    unused = report['unused']
    if unused and not any('Error' in str(u) for u in unused):
        click.echo(f"\n⚠️  Potentially Unused Imports ({len(unused)}):")
        for name in unused:
            click.echo(f"  - {name}")


@main.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help='Output format')
def smells(file_path, format):
    """Detect code smells and anti-patterns."""
    try:
        detector = CodeSmellDetector(file_path)
        report = detector.detect_all_smells()
        
        if format == 'json':
            click.echo(json.dumps(report, indent=2))
        else:
            _print_smell_report(report)
    except Exception as e:
        click.echo(f"Error detecting code smells: {e}", err=True)


def _print_smell_report(report):
    """Print code smell report in human-readable format."""
    click.echo(f"\n👃 Code Smell Detection: {report['file']}\n")
    click.echo("=" * 60)
    
    total_smells = 0
    
    # Long methods
    long_methods = report['long_methods']
    if long_methods and 'error' not in long_methods[0]:
        click.echo(f"\n📏 Long Methods ({len(long_methods)}):")
        for item in long_methods:
            click.echo(f"  ⚠️  {item['name']} (line {item['line']}): {item['length']} lines")
            total_smells += 1
    
    # Large classes
    large_classes = report['large_classes']
    if large_classes and 'error' not in large_classes[0]:
        click.echo(f"\n📦 Large Classes ({len(large_classes)}):")
        for item in large_classes:
            click.echo(f"  ⚠️  {item['name']} (line {item['line']}): {item['length']} lines, {item['methods']} methods")
            total_smells += 1
    
    # Too many parameters
    many_params = report['too_many_parameters']
    if many_params and 'error' not in many_params[0]:
        click.echo(f"\n🔢 Too Many Parameters ({len(many_params)}):")
        for item in many_params:
            click.echo(f"  ⚠️  {item['name']} (line {item['line']}): {item['parameters']} parameters")
            total_smells += 1
    
    # Deep nesting
    deep_nesting = report['deep_nesting']
    if deep_nesting and 'error' not in deep_nesting[0]:
        click.echo(f"\n🪆 Deep Nesting ({len(deep_nesting)}):")
        for item in deep_nesting:
            click.echo(f"  ⚠️  {item['name']} (line {item['line']}): depth {item['depth']}")
            total_smells += 1
    
    # Duplicate code
    duplicates = report['duplicate_code']
    if duplicates and 'error' not in duplicates[0]:
        click.echo(f"\n📋 Duplicate Code ({len(duplicates)}):")
        for item in duplicates:
            click.echo(f"  ⚠️  {item['function1']} and {item['function2']} (line {item['line']})")
            total_smells += 1
    
    click.echo(f"\n{'='*60}")
    click.echo(f"Total code smells detected: {total_smells}")


@main.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help='Output format')
def analyze(file_path, format):
    """Run all analysis tools on a file."""
    try:
        # Run all analyses
        complexity_analyzer = ComplexityAnalyzer(file_path)
        dependency_analyzer = DependencyAnalyzer(file_path)
        smell_detector = CodeSmellDetector(file_path)
        
        report = {
            'file': file_path,
            'complexity': complexity_analyzer.get_full_report(),
            'dependencies': {
                'file': file_path,
                'imports': dependency_analyzer.extract_imports(),
                'counts': dependency_analyzer.count_dependencies(),
                'unused': dependency_analyzer.find_unused_imports(),
            },
            'smells': smell_detector.detect_all_smells(),
        }
        
        if format == 'json':
            click.echo(json.dumps(report, indent=2))
        else:
            click.echo(f"\n🔍 Complete Analysis: {file_path}\n")
            click.echo("=" * 60)
            _print_complexity_report(report['complexity'])
            click.echo("\n")
            _print_dependency_report(report['dependencies'])
            click.echo("\n")
            _print_smell_report(report['smells'])
    except Exception as e:
        click.echo(f"Error running analysis: {e}", err=True)


@main.command()
@click.argument('project_path', type=click.Path(exists=True))
@click.option('--format', type=click.Choice(['text', 'json']), default='text', help='Output format')
def project(project_path, format):
    """Analyze all Python files in a project."""
    try:
        analyzer = ProjectDependencyAnalyzer(project_path)
        results = analyzer.analyze_project()
        
        if format == 'json':
            click.echo(json.dumps(results, indent=2))
        else:
            click.echo(f"\n📁 Project Analysis: {project_path}\n")
            click.echo("=" * 60)
            click.echo(f"Analyzed {len(results)} Python files\n")
            
            for file_path, data in results.items():
                if 'error' in data:
                    click.echo(f"❌ {file_path}: {data['error']}")
                else:
                    counts = data['counts']
                    unused_count = len(data['unused'])
                    click.echo(f"📄 {file_path}")
                    click.echo(f"   Imports: {counts['total']} total, {unused_count} potentially unused")
    except Exception as e:
        click.echo(f"Error analyzing project: {e}", err=True)


if __name__ == '__main__':
    main()
