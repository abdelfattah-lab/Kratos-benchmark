"""
Repository configuration constants.

This file provides the repository root path as a constant that can be imported
by scripts anywhere in the repository, avoiding relative path issues.
"""

from pathlib import Path

# The root directory of the Kratos-benchmark repository
REPO_ROOT = Path(__file__).parent.resolve()

# Common paths derived from REPO_ROOT
VERILOG_DIR = REPO_ROOT / "verilog"
