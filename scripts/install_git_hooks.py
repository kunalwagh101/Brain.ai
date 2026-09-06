#!/usr/bin/env python3
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
hooks = root / ".githooks"
subprocess.run(["git", "config", "core.hooksPath", str(hooks)], cwd=root, check=True)
print(f"Configured git hooks path: {hooks}")
