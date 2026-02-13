"""Dependency analyzer for Python code."""

import ast
import os
from typing import Dict, List, Set
from collections import defaultdict


class DependencyAnalyzer:
    """Analyzes code dependencies and imports."""

    def __init__(self, file_path: str):
        """Initialize with a Python file path."""
        self.file_path = file_path
        with open(file_path, 'r', encoding='utf-8') as f:
            self.code = f.read()

    def extract_imports(self) -> Dict:
        """Extract all imports from the file."""
        try:
            tree = ast.parse(self.code)
            imports = {
                'standard': [],
                'third_party': [],
                'local': [],
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports['third_party'].append({
                            'module': alias.name,
                            'alias': alias.asname,
                            'line': node.lineno,
                        })
                elif isinstance(node, ast.ImportFrom):
                    module = node.module if node.module else ''
                    for alias in node.names:
                        imports['third_party'].append({
                            'module': module,
                            'name': alias.name,
                            'alias': alias.asname,
                            'line': node.lineno,
                        })
            
            return imports
        except Exception as e:
            return {'error': str(e)}

    def count_dependencies(self) -> Dict:
        """Count the number of dependencies."""
        imports = self.extract_imports()
        if 'error' in imports:
            return imports
        
        return {
            'total': (
                len(imports['standard']) +
                len(imports['third_party']) +
                len(imports['local'])
            ),
            'standard': len(imports['standard']),
            'third_party': len(imports['third_party']),
            'local': len(imports['local']),
        }

    def find_unused_imports(self) -> List[str]:
        """Find potentially unused imports (basic heuristic)."""
        try:
            tree = ast.parse(self.code)
            imported_names = set()
            used_names = set()
            
            # Collect imported names
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.asname if alias.asname else alias.name.split('.')[0]
                        imported_names.add(name)
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        name = alias.asname if alias.asname else alias.name
                        imported_names.add(name)
            
            # Collect used names (simplified)
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    used_names.add(node.id)
                elif isinstance(node, ast.Attribute):
                    # Get the root name
                    root = node
                    while isinstance(root, ast.Attribute):
                        root = root.value
                    if isinstance(root, ast.Name):
                        used_names.add(root.id)
            
            # Find unused
            unused = list(imported_names - used_names)
            return unused
        except Exception as e:
            return [f"Error: {str(e)}"]


class ProjectDependencyAnalyzer:
    """Analyzes dependencies across a project."""

    def __init__(self, root_path: str):
        """Initialize with project root path."""
        self.root_path = root_path
        self.dependencies = defaultdict(list)

    def analyze_project(self) -> Dict:
        """Analyze all Python files in the project."""
        python_files = []
        
        for root, dirs, files in os.walk(self.root_path):
            # Skip common directories
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'venv', 'env', '.tox']]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    python_files.append(file_path)
        
        results = {}
        for file_path in python_files:
            try:
                analyzer = DependencyAnalyzer(file_path)
                rel_path = os.path.relpath(file_path, self.root_path)
                results[rel_path] = {
                    'imports': analyzer.extract_imports(),
                    'counts': analyzer.count_dependencies(),
                    'unused': analyzer.find_unused_imports(),
                }
            except Exception as e:
                results[file_path] = {'error': str(e)}
        
        return results
