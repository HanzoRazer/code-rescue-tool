"""Code smell detector for identifying common anti-patterns."""

import ast
import os
from typing import Dict, List


class CodeSmellDetector:
    """Detects various code smells in Python code."""

    def __init__(self, file_path: str):
        """Initialize with a Python file path."""
        self.file_path = file_path
        with open(file_path, 'r', encoding='utf-8') as f:
            self.code = f.read()

    def detect_long_methods(self, threshold: int = 50) -> List[Dict]:
        """Detect methods/functions longer than threshold."""
        try:
            tree = ast.parse(self.code)
            long_methods = []
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if hasattr(node, 'end_lineno') and hasattr(node, 'lineno'):
                        length = node.end_lineno - node.lineno + 1
                        if length > threshold:
                            long_methods.append({
                                'name': node.name,
                                'line': node.lineno,
                                'length': length,
                                'smell': 'Long Method',
                            })
            
            return long_methods
        except Exception as e:
            return [{'error': str(e)}]

    def detect_large_classes(self, threshold: int = 200) -> List[Dict]:
        """Detect classes larger than threshold lines."""
        try:
            tree = ast.parse(self.code)
            large_classes = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    if hasattr(node, 'end_lineno') and hasattr(node, 'lineno'):
                        length = node.end_lineno - node.lineno + 1
                        method_count = sum(
                            1 for n in ast.walk(node)
                            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                        )
                        if length > threshold:
                            large_classes.append({
                                'name': node.name,
                                'line': node.lineno,
                                'length': length,
                                'methods': method_count,
                                'smell': 'Large Class',
                            })
            
            return large_classes
        except Exception as e:
            return [{'error': str(e)}]

    def detect_too_many_parameters(self, threshold: int = 5) -> List[Dict]:
        """Detect functions with too many parameters."""
        try:
            tree = ast.parse(self.code)
            functions_with_many_params = []
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    param_count = len(node.args.args)
                    if param_count > threshold:
                        functions_with_many_params.append({
                            'name': node.name,
                            'line': node.lineno,
                            'parameters': param_count,
                            'smell': 'Too Many Parameters',
                        })
            
            return functions_with_many_params
        except Exception as e:
            return [{'error': str(e)}]

    def detect_deep_nesting(self, threshold: int = 4) -> List[Dict]:
        """Detect deeply nested code."""
        try:
            tree = ast.parse(self.code)
            deep_nesting = []
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    max_depth = self._get_max_nesting_depth(node)
                    if max_depth > threshold:
                        deep_nesting.append({
                            'name': node.name,
                            'line': node.lineno,
                            'depth': max_depth,
                            'smell': 'Deep Nesting',
                        })
            
            return deep_nesting
        except Exception as e:
            return [{'error': str(e)}]

    def _get_max_nesting_depth(self, node: ast.AST, current_depth: int = 0) -> int:
        """Recursively calculate maximum nesting depth."""
        max_depth = current_depth
        
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

    def detect_duplicate_code(self) -> List[Dict]:
        """Detect potential duplicate code (basic heuristic)."""
        try:
            tree = ast.parse(self.code)
            function_bodies = {}
            duplicates = []
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Get a simplified representation of the function body
                    body_str = ast.dump(node)
                    
                    if body_str in function_bodies:
                        duplicates.append({
                            'function1': function_bodies[body_str],
                            'function2': node.name,
                            'line': node.lineno,
                            'smell': 'Duplicate Code',
                        })
                    else:
                        function_bodies[body_str] = node.name
            
            return duplicates
        except Exception as e:
            return [{'error': str(e)}]

    def detect_all_smells(self) -> Dict:
        """Run all smell detectors and return comprehensive report."""
        return {
            'file': self.file_path,
            'long_methods': self.detect_long_methods(),
            'large_classes': self.detect_large_classes(),
            'too_many_parameters': self.detect_too_many_parameters(),
            'deep_nesting': self.detect_deep_nesting(),
            'duplicate_code': self.detect_duplicate_code(),
        }
