"""Ingest module - load run_result (v1 or v2) from code-analysis-tool."""

from code_rescue.ingest.run_result_loader import load_run_result, RunResult

__all__ = ["load_run_result", "RunResult"]
