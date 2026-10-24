"""Content hashing for SKILL.md text, per SPEC.md §3.3.

Normalisation: line endings to LF, trailing whitespace stripped per line,
trailing blank lines removed, exactly one trailing newline. The hash is
SHA-256 of the normalised UTF-8 bytes, rendered as ``sha256:<hex>``.
"""

import hashlib
from pathlib import Path


def normalise_skill_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def hash_skill_text(text: str) -> str:
    digest = hashlib.sha256(normalise_skill_text(text).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def hash_skill_file(path: str | Path) -> str:
    return hash_skill_text(Path(path).read_text(encoding="utf-8"))
