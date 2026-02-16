"""
Tests for the recipe schema validation script.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "validate_recipes.py"


def run_validate(args: list[str]) -> tuple[int, str, str]:
    """Run validate_recipes.py and return (exit_code, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)] + args,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    return result.returncode, result.stdout, result.stderr


def test_validate_valid_file():
    """Validation script passes for valid sample-recipes.json"""
    exit_code, stdout, _ = run_validate(["sample-recipes.json"])
    assert exit_code == 0
    assert "passed schema validation" in stdout


def test_validate_invalid_json(tmp_path):
    """Validation script fails for invalid JSON"""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ invalid json")
    exit_code, stdout, _ = run_validate([str(bad_file)])
    assert exit_code == 1
    assert "Invalid JSON" in stdout or "invalid" in stdout.lower()


def test_validate_not_array(tmp_path):
    """Validation script fails when root is not an array"""
    bad_file = tmp_path / "object.json"
    bad_file.write_text('{"key": "value"}')
    exit_code, stdout, _ = run_validate([str(bad_file)])
    assert exit_code == 1
    assert "array" in stdout.lower()


def test_validate_invalid_recipe_schema(tmp_path):
    """Validation script fails for recipe with empty ingredients"""
    invalid = [
        {
            "id": "bad-001",
            "title": "Test",
            "description": "Desc",
            "ingredients": [],  # Invalid
            "instructions": ["Step 1"],
            "tags": [],
            "cuisine": None,
        }
    ]
    bad_file = tmp_path / "invalid.json"
    bad_file.write_text(json.dumps(invalid))
    exit_code, stdout, _ = run_validate([str(bad_file)])
    assert exit_code == 1
    assert "index" in stdout or "Recipe" in stdout
