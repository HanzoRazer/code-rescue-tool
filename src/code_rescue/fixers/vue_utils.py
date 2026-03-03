"""Shared Vue fixer utilities."""

from __future__ import annotations

import re
from pathlib import Path


def to_pascal(name: str) -> str:
    """Convert name to PascalCase."""
    return "".join(word.capitalize() for word in re.split(r"[-_\s]+", name))


def to_kebab(name: str) -> str:
    """Convert PascalCase to kebab-case."""
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def extract_component_name(file_path: str) -> str:
    """Extract component name from file path."""
    return Path(file_path).stem
