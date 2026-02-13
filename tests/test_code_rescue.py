"""Unit tests for the code rescue tools."""

import os
import sys
import unittest
from code_rescue.complexity import ComplexityAnalyzer
from code_rescue.dependencies import DependencyAnalyzer, ProjectDependencyAnalyzer
from code_rescue.smells import CodeSmellDetector


class TestComplexityAnalyzer(unittest.TestCase):
    """Test cases for ComplexityAnalyzer."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_file = os.path.join(os.path.dirname(__file__), '..', 'examples', 'spaghetti_code.py')
        self.analyzer = ComplexityAnalyzer(self.test_file)
    
    def test_calculate_cyclomatic_complexity(self):
        """Test cyclomatic complexity calculation."""
        results = self.analyzer.calculate_cyclomatic_complexity()
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        
        # Check that we found the high complexity functions
        complex_functions = [r for r in results if r.get('complexity', 0) > 10]
        self.assertGreater(len(complex_functions), 0)
    
    def test_analyze_raw_metrics(self):
        """Test raw code metrics analysis."""
        metrics = self.analyzer.analyze_raw_metrics()
        self.assertIn('loc', metrics)
        self.assertIn('lloc', metrics)
        self.assertIn('sloc', metrics)
        self.assertGreater(metrics['loc'], 0)
    
    def test_find_long_functions(self):
        """Test finding long functions."""
        long_functions = self.analyzer.find_long_functions(threshold=50)
        self.assertIsInstance(long_functions, list)
        # Our example file has at least one long function
        self.assertGreater(len(long_functions), 0)
    
    def test_calculate_nesting_depth(self):
        """Test nesting depth calculation."""
        results = self.analyzer.calculate_nesting_depth()
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        
        # Check for deeply nested functions
        deep_functions = [r for r in results if r.get('max_nesting', 0) > 4]
        self.assertGreater(len(deep_functions), 0)
    
    def test_get_full_report(self):
        """Test comprehensive report generation."""
        report = self.analyzer.get_full_report()
        self.assertIn('file', report)
        self.assertIn('cyclomatic_complexity', report)
        self.assertIn('raw_metrics', report)
        self.assertIn('long_functions', report)
        self.assertIn('nesting_depth', report)


class TestDependencyAnalyzer(unittest.TestCase):
    """Test cases for DependencyAnalyzer."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_file = os.path.join(os.path.dirname(__file__), '..', 'examples', 'spaghetti_code.py')
        self.analyzer = DependencyAnalyzer(self.test_file)
    
    def test_extract_imports(self):
        """Test import extraction."""
        imports = self.analyzer.extract_imports()
        self.assertIn('standard', imports)
        self.assertIn('third_party', imports)
        self.assertIn('local', imports)
    
    def test_count_dependencies(self):
        """Test dependency counting."""
        counts = self.analyzer.count_dependencies()
        self.assertIn('total', counts)
        self.assertGreater(counts['total'], 0)
    
    def test_find_unused_imports(self):
        """Test unused import detection."""
        unused = self.analyzer.find_unused_imports()
        self.assertIsInstance(unused, list)


class TestCodeSmellDetector(unittest.TestCase):
    """Test cases for CodeSmellDetector."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_file = os.path.join(os.path.dirname(__file__), '..', 'examples', 'spaghetti_code.py')
        self.detector = CodeSmellDetector(self.test_file)
    
    def test_detect_long_methods(self):
        """Test long method detection."""
        long_methods = self.detector.detect_long_methods(threshold=50)
        self.assertIsInstance(long_methods, list)
        self.assertGreater(len(long_methods), 0)
    
    def test_detect_large_classes(self):
        """Test large class detection."""
        large_classes = self.detector.detect_large_classes(threshold=100)
        self.assertIsInstance(large_classes, list)
    
    def test_detect_too_many_parameters(self):
        """Test detection of functions with too many parameters."""
        many_params = self.detector.detect_too_many_parameters(threshold=5)
        self.assertIsInstance(many_params, list)
        # Our example has a function with 11 parameters
        self.assertGreater(len(many_params), 0)
    
    def test_detect_deep_nesting(self):
        """Test deep nesting detection."""
        deep_nesting = self.detector.detect_deep_nesting(threshold=4)
        self.assertIsInstance(deep_nesting, list)
        self.assertGreater(len(deep_nesting), 0)
    
    def test_detect_duplicate_code(self):
        """Test duplicate code detection."""
        duplicates = self.detector.detect_duplicate_code()
        self.assertIsInstance(duplicates, list)
    
    def test_detect_all_smells(self):
        """Test comprehensive smell detection."""
        report = self.detector.detect_all_smells()
        self.assertIn('file', report)
        self.assertIn('long_methods', report)
        self.assertIn('large_classes', report)
        self.assertIn('too_many_parameters', report)
        self.assertIn('deep_nesting', report)
        self.assertIn('duplicate_code', report)


if __name__ == '__main__':
    unittest.main()
