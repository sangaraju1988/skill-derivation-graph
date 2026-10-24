"""Content hashing for SKILL.md text, per SPEC.md §3.3.

Normalisation: line endings to LF, trailing whitespace stripped per line,
trailing blank lines removed, exactly one trailing newline. Lineage keys
(``derived-from`` and ``derived-from-hash``) inside the YAML frontmatter are
removed before hashing, so that adding lineage to a verbatim copy does not
change its content identity. The hash is SHA-256 of the normalised UTF-8
bytes, rendered as ``sha256:<hex>``.
"""

import hashlib
from pathlib import Path

LINEAGE_KEYS = ("derived-from", "derived-from-hash")


def _strip_lineage_keys(lines: list[str]) -> list[str]:
    """Drop lineage keys from a leading ``---`` frontmatter block only."""
    if not lines or lines[0] != "---":
        return lines
    try:
        end = lines.index("---", 1)
    except ValueError:
        return lines
    front = [
        line
        for line in lines[1:end]
        if not any(line.lstrip().startswith(f"{key}:") for key in LINEAGE_KEYS)
    ]
    return [lines[0], *front, *lines[end:]]


def normalise_skill_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    lines = _strip_lineage_keys(lines)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def hash_skill_text(text: str) -> str:
    digest = hashlib.sha256(normalise_skill_text(text).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def hash_skill_file(path: str | Path) -> str:
    return hash_skill_text(Path(path).read_text(encoding="utf-8"))


def classify_derivation(child_text: str, parent_hash: str) -> str:
    """``verbatim`` if the child's normalised hash equals ``derived-from-hash``,
    else ``modified``. Derivation is computed, never declared."""
    return "verbatim" if hash_skill_text(child_text) == parent_hash else "modified"
