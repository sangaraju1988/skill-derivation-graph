"""Fix-propagation walk and load-time check, per SPEC.md §6.

A patch event (§6.1) is: skill S publishes V' with ``patches = V``. The walk
starts at the vulnerable version(s) of S and follows DERIVED_FROM edges
*forward* (parent -> children, transitively, breadth-first), carrying a flag
for whether a ``modified`` edge has been crossed:

- descendants through only ``verbatim`` edges -> ``stale-vulnerable``
- descendants through at least one ``modified`` edge -> ``stale-review``
- V' itself, later versions of S, and anything derived from them -> ``current``
- pre-patch versions of S -> ``superseded``
- versions whose parent chain does not resolve -> ``unresolved``
- everything else -> ``unaffected``

S may sit anywhere in the graph (a source skill, or itself a copy/fork):
the walk does not depend on where S's own ancestry leads.
"""

import re
from collections import deque

from .model import DerivationGraph

LOAD_DECISION = {
    "current": "allow",
    "unaffected": "allow",
    "stale-vulnerable": "block",
    "stale-review": "warn-review",
    "superseded": "warn-superseded",
    "unresolved": "warn-unresolved",
}

_SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+.*)?$")


def semver_key(version: str):
    """Sort key for MAJOR.MINOR.PATCH[-pre]; a pre-release sorts below its release.

    Returns None for a version string that is not semantic-versioned.
    """
    m = _SEMVER.match(version)
    if not m:
        return None
    major, minor, patch, pre = m.groups()
    return (int(major), int(minor), int(patch), 0 if pre else 1, pre or "")


def _vulnerable_versions(graph, source_skill_id, patched_version, vulnerable_version):
    """Resolve V: explicit argument, else the patched node's ``patches`` field,
    else every version of S that sorts below V' (§5)."""
    if vulnerable_version:
        return {vulnerable_version}
    patched = graph.versions.get((source_skill_id, patched_version))
    if patched is not None and patched.patches:
        return {patched.patches}
    target = semver_key(patched_version)
    out = set()
    for skill_id, version in graph.versions:
        if skill_id != source_skill_id or version == patched_version:
            continue
        key = semver_key(version)
        if target is None or key is None or key < target:
            out.add(version)
    return out


def _forward_bfs(graph, start):
    """Yield (key, hops, crossed_modified) for every descendant of ``start``."""
    queue = deque([(start, 0, False)])
    seen = {start}
    while queue:
        key, hops, modified = queue.popleft()
        for child in graph.children_of(key):
            if child in seen:
                continue
            seen.add(child)
            child_modified = modified or graph.versions[child].derivation == "modified"
            yield child, hops + 1, child_modified
            queue.append((child, hops + 1, child_modified))


def propagate_fix(
    graph: DerivationGraph,
    source_skill_id: str,
    patched_version: str,
    vulnerable_version: str | None = None,
) -> dict[tuple[str, str], dict]:
    """Walk the graph from a patch event and return a state per version.

    ``source_skill_id`` is the patched skill S; ``patched_version`` is V'.
    ``vulnerable_version`` is V; if omitted it is taken from V'.patches when
    V' is in the graph, else every version of S below V' is treated as
    vulnerable.
    """
    results: dict[tuple[str, str], dict] = {}
    vulnerable = _vulnerable_versions(graph, source_skill_id, patched_version, vulnerable_version)

    # 1. Versions of S itself.
    patched_key = semver_key(patched_version)
    current_roots = []
    for key in graph.versions:
        skill_id, version = key
        if skill_id != source_skill_id:
            continue
        if version in vulnerable:
            results[key] = {"state": "superseded", "hops": 0,
                            "reason": f"superseded by {patched_version}"}
        else:
            vk = semver_key(version)
            if version == patched_version or (
                patched_key is not None and vk is not None and vk >= patched_key
            ):
                results[key] = {"state": "current", "hops": 0,
                                "reason": "is the patched version or a later release"}
                current_roots.append(key)

    # 2. Descendants of fixed versions are current.
    for root in current_roots:
        for key, hops, _ in _forward_bfs(graph, root):
            results.setdefault(key, {"state": "current", "hops": hops,
                                     "reason": "derived from the patched version"})

    # 3. Descendants of vulnerable versions are stale (nearest path wins).
    for version in sorted(vulnerable):
        root = (source_skill_id, version)
        if root not in graph.versions:
            continue
        for key, hops, modified in _forward_bfs(graph, root):
            if key in results and results[key]["state"] != "stale-vulnerable":
                continue
            if modified:
                results[key] = {"state": "stale-review", "hops": hops,
                                "reason": "descends from a pre-patch version through a "
                                "modified edge; review whether the patch applies"}
            else:
                results.setdefault(key, {"state": "stale-vulnerable", "hops": hops,
                                         "reason": "descends from a pre-patch version through "
                                         "verbatim edges only; the vulnerability is inherited "
                                         "by construction"})

    # 4. Everything else: unresolved if its parent chain breaks, else unaffected.
    for key in graph.versions:
        if key in results:
            continue
        _, _, missing = graph.walk_to_root(key)
        if missing:
            results[key] = {"state": "unresolved", "hops": None,
                            "reason": "referenced parent is absent from the graph"}
        else:
            results[key] = {"state": "unaffected", "hops": None,
                            "reason": "does not descend from the patched skill"}
    return results


def check_before_load(
    graph: DerivationGraph,
    key: tuple[str, str],
    states: dict[tuple[str, str], dict],
) -> str:
    """Load-time decision for one version, given propagation ``states``.

    Returns one of: allow, block, warn-review, warn-superseded,
    warn-unresolved. A version absent from the graph, or with an
    unresolvable parent, is never reported as current.
    """
    if key not in graph.versions:
        return "warn-unresolved"
    state = states.get(key, {}).get("state", "unresolved")
    return LOAD_DECISION.get(state, "warn-unresolved")
