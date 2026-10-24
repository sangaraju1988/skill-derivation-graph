"""Derivation-graph model, per SPEC.md §3–§4.

A SkillVersion is one immutable release of a skill. A DerivationGraph holds
versions keyed by (skill_id, version); each version points at its parent
version (or None for a source skill) via a DERIVED_FROM edge, and records
whether that derivation was ``verbatim`` or ``modified``.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SkillVersion:
    skill_id: str
    version: str
    author: str
    content_hash: str
    parent_skill_id: str | None = None
    parent_version: str | None = None
    derivation: str | None = None  # "verbatim" | "modified" | None (source)
    created_at: str | None = None
    supersedes: str | None = None
    patches: str | None = None
    # Example-only helper: the SKILL.md text the hash was computed from.
    # Not part of the provenance record in SPEC.md §4.
    skill_text: str | None = field(default=None, compare=False)

    @property
    def key(self) -> tuple[str, str]:
        return (self.skill_id, self.version)

    @property
    def parent_key(self) -> tuple[str, str] | None:
        if self.parent_skill_id is None:
            return None
        return (self.parent_skill_id, self.parent_version)

    @classmethod
    def from_dict(cls, data: dict) -> "SkillVersion":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


class DerivationGraph:
    """A small in-memory derivation graph."""

    def __init__(self) -> None:
        self.versions: dict[tuple[str, str], SkillVersion] = {}

    def add(self, version: SkillVersion) -> None:
        if version.key in self.versions:
            raise ValueError(f"duplicate version: {version.key}")
        self.versions[version.key] = version

    def children_of(self, key: tuple[str, str]) -> list[tuple[str, str]]:
        return [v.key for v in self.versions.values() if v.parent_key == key]

    def walk_to_root(self, key: tuple[str, str]):
        """Walk parent pointers from ``key`` towards a source skill.

        Returns (edges, reached_key, missing_parent) where ``edges`` is the
        list of derivation labels on the path (nearest edge first, excluding
        the reached node's own derivation), ``reached_key`` is the key the
        walk stopped at, and ``missing_parent`` is True when a referenced
        parent is absent from the graph.
        """
        edges: list[str | None] = []
        current = key
        seen: set[tuple[str, str]] = set()
        while True:
            node = self.versions.get(current)
            if node is None:
                return edges, current, True
            if current in seen:
                raise ValueError(f"derivation cycle at {current}")
            seen.add(current)
            parent = node.parent_key
            if parent is None:
                return edges, current, False
            edges.append(node.derivation)
            current = parent
