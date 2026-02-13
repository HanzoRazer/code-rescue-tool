"""Complexity analyzer for Python code."""

import ast
import os
from typing import Dict, List, Optional
from radon.complexity import cc_visit
from radon.raw import analyze


class ComplexityAnalyzer:
    """Analyzes code complexity metrics."""

    def __init__(self, file_path: str):
        """Initialize with a Python file path."""
        self.file_path = file_path
        with open(file_path, 'r', encoding='utf-8') as f:
            self.code = f.read()

    def calculate_cyclomatic_complexity(self) -> List[Dict]:
        """Calculate cyclomatic complexity for all functions/methods."""
        try:
            results = cc_visit(self.code)
            return [
                {
                    'name': item.name,
                    'type': item.letter,
                    'complexity': item.complexity,
                    'line': item.lineno,
                    'col': item.col_offset,
                }
                for item in results
            ]
        except Exception as e:
            return [{'error': str(e)}]

    def analyze_raw_metrics(self) -> Dict:
        """Analyze raw code metrics (LOC, SLOC, comments, etc.)."""
        try:
            metrics = analyze(self.code)
            return {
                'loc': metrics.loc,
                'lloc': metrics.lloc,
                'sloc': metrics.sloc,
                'comments': metrics.comments,
                'multi': metrics.multi,
                'blank': metrics.blank,
            }
        except Exception as e:
            return {'error': str(e)}

    def find_long_functions(self, threshold: int = 50) -> List[Dict]:
        """Find functions longer than threshold lines."""
        try:
            tree = ast.parse(self.code)
            long_functions = []
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Calculate function length
                    if hasattr(node, 'end_lineno') and hasattr(node, 'lineno'):
                        length = node.end_lineno - node.lineno + 1
                        if length > threshold:
                            long_functions.append({
                                'name': node.name,
                                'line': node.lineno,
                                'length': length,
                            })
            
            return long_functions
        except Exception as e:
            return [{'error': str(e)}]

    def calculate_nesting_depth(self) -> List[Dict]:
        """Calculate maximum nesting depth in functions."""
        try:
            tree = ast.parse(self.code)
            results = []
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    max_depth = self._get_max_nesting_depth(node)
                    results.append({
                        'name': node.name,
                        'line': node.lineno,
                        'max_nesting': max_depth,
                    })
            
            return results
        except Exception as e:
            return [{'error': str(e)}]

    def _get_max_nesting_depth(self, node: ast.AST, current_depth: int = 0) -> int:
        """Recursively calculate maximum nesting depth."""
        max_depth = current_depth
        
        # Nodes that increase nesting depth
        nesting_nodes = (
            ast.If, ast.For, ast.While, ast.With, ast.Try,
            ast.ExceptHandler, ast.AsyncFor, ast.AsyncWith
        )
        
        for child in ast.iter_child_nodes(node):
            if isinstance(child, nesting_nodes):
                depth = self._get_max_nesting_depth(child, current_depth + 1)
                max_depth = max(max_depth, depth)
            else:
                depth = self._get_max_nesting_depth(child, current_depth)
                max_depth = max(max_depth, depth)
        
        return max_depth

    def get_full_report(self) -> Dict:
        """Get a comprehensive complexity report."""
        return {
            'file': self.file_path,
            'cyclomatic_complexity': self.calculate_cyclomatic_complexity(),
            'raw_metrics': self.analyze_raw_metrics(),
            'long_functions': self.find_long_functions(),
            'nesting_depth': self.calculate_nesting_depth(),
        }
