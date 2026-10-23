"""Fail if obvious live credentials are present in tracked project text files."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache"}
SKIP_FILES = {".env"}
TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".env", ".example"
}
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{24,}"),
    re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
    re.compile(r"(?i)PAYPAL_CLIENT_SECRET\s*=\s*[^\s#]{12,}"),
)


def iter_tracked_files():
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        path = PROJECT_ROOT / raw.decode("utf-8", errors="ignore")
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".env.example":
            continue
        yield path


def iter_text_files():
    """Fallback for environments without Git metadata."""
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".env.example":
            continue
        yield path


def main() -> int:
    findings: list[tuple[str, int]] = []
    try:
        candidates = list(iter_tracked_files())
    except (OSError, subprocess.SubprocessError):
        candidates = list(iter_text_files())
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in SECRET_PATTERNS):
                findings.append((str(path.relative_to(PROJECT_ROOT)), line_number))
    if findings:
        for path, line_number in findings:
            print(f"Potential secret at {path}:{line_number}")
        return 1
    print("No obvious live secrets found in project text files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

