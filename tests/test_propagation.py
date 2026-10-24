"""Tests for the fix-propagation walk (SPEC.md §6).

Standard library unittest only. Run from the repo root:
    python3 -m unittest discover tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skillgraph import (  # noqa: E402
    DerivationGraph,
    SkillVersion,
    check_before_load,
    hash_skill_text,
    propagate_fix,
)


def _version(skill_id, version, parent=None, derivation=None):
    return SkillVersion(
        skill_id=skill_id,
        version=version,
        author="synthetic@example.dev",
        content_hash="sha256:synthetic",
        parent_skill_id=parent[0] if parent else None,
        parent_version=parent[1] if parent else None,
        derivation=derivation,
    )


def build_chain():
    """source -> verbatim copy -> modified fork, plus an unrelated skill."""
    graph = DerivationGraph()
    graph.add(_version("doc-summarizer", "1.0.0"))
    graph.add(_version("doc-summarizer-copy", "1.0.0", ("doc-summarizer", "1.0.0"), "verbatim"))
    graph.add(_version("doc-summarizer-fork", "1.0.0", ("doc-summarizer-copy", "1.0.0"), "modified"))
    graph.add(_version("unrelated-skill", "2.0.0"))
    return graph


class TestPropagation(unittest.TestCase):
    def test_patch_marks_verbatim_copy_vulnerable_and_fork_for_review(self):
        graph = build_chain()
        states = propagate_fix(graph, "doc-summarizer", "1.1.0")
        self.assertEqual(states[("doc-summarizer", "1.0.0")]["state"], "superseded")
        self.assertEqual(states[("doc-summarizer-copy", "1.0.0")]["state"], "stale-vulnerable")
        self.assertEqual(states[("doc-summarizer-copy", "1.0.0")]["hops"], 1)
        self.assertEqual(states[("doc-summarizer-fork", "1.0.0")]["state"], "stale-review")
        self.assertEqual(states[("doc-summarizer-fork", "1.0.0")]["hops"], 2)
        self.assertEqual(states[("unrelated-skill", "2.0.0")]["state"], "unaffected")

    def test_load_decisions_follow_states(self):
        graph = build_chain()
        states = propagate_fix(graph, "doc-summarizer", "1.1.0")
        self.assertEqual(
            check_before_load(graph, ("doc-summarizer-copy", "1.0.0"), states), "block"
        )
        self.assertEqual(
            check_before_load(graph, ("doc-summarizer-fork", "1.0.0"), states), "warn-review"
        )
        self.assertEqual(
            check_before_load(graph, ("unrelated-skill", "2.0.0"), states), "allow"
        )

    def test_unresolved_parent_is_never_current(self):
        graph = DerivationGraph()
        graph.add(_version("orphan-copy", "1.0.0", ("missing-source", "9.9.9"), "verbatim"))
        states = propagate_fix(graph, "doc-summarizer", "1.1.0")
        self.assertEqual(states[("orphan-copy", "1.0.0")]["state"], "unresolved")
        self.assertEqual(
            check_before_load(graph, ("orphan-copy", "1.0.0"), states), "warn-unresolved"
        )


class TestPatchEventEdgeCases(unittest.TestCase):
    def test_patching_a_mid_chain_fork_reaches_its_descendants(self):
        graph = build_chain()
        graph.add(_version("fork-copy", "1.0.0", ("doc-summarizer-fork", "1.0.0"), "verbatim"))
        graph.add(_version("fork-variant", "1.0.0", ("doc-summarizer-fork", "1.0.0"), "modified"))
        states = propagate_fix(graph, "doc-summarizer-fork", "1.0.1")
        self.assertEqual(states[("doc-summarizer-fork", "1.0.0")]["state"], "superseded")
        self.assertEqual(states[("fork-copy", "1.0.0")]["state"], "stale-vulnerable")
        self.assertEqual(states[("fork-copy", "1.0.0")]["hops"], 1)
        self.assertEqual(states[("fork-variant", "1.0.0")]["state"], "stale-review")
        # Ancestors of the patched fork are not affected by its patch.
        self.assertEqual(states[("doc-summarizer", "1.0.0")]["state"], "unaffected")
        self.assertEqual(states[("doc-summarizer-copy", "1.0.0")]["state"], "unaffected")

    def test_later_release_is_not_reported_superseded(self):
        graph = build_chain()
        graph.add(_version("doc-summarizer", "1.2.0"))
        states = propagate_fix(graph, "doc-summarizer", "1.1.0")
        self.assertEqual(states[("doc-summarizer", "1.2.0")]["state"], "current")
        self.assertEqual(states[("doc-summarizer", "1.0.0")]["state"], "superseded")

    def test_patches_field_limits_the_vulnerable_set(self):
        graph = DerivationGraph()
        graph.add(_version("s", "0.9.0"))
        graph.add(_version("s", "1.0.0"))
        graph.add(_version("old-copy", "1.0.0", ("s", "0.9.0"), "verbatim"))
        graph.add(_version("new-copy", "1.0.0", ("s", "1.0.0"), "verbatim"))
        graph.add(SkillVersion(skill_id="s", version="1.0.1", author="x",
                               content_hash="sha256:synthetic", patches="1.0.0"))
        states = propagate_fix(graph, "s", "1.0.1")
        self.assertEqual(states[("new-copy", "1.0.0")]["state"], "stale-vulnerable")
        self.assertEqual(states[("old-copy", "1.0.0")]["state"], "unaffected")

    def test_copy_of_patched_version_is_current(self):
        graph = build_chain()
        graph.add(_version("doc-summarizer", "1.1.0"))
        graph.add(_version("new-copy", "1.1.0", ("doc-summarizer", "1.1.0"), "verbatim"))
        states = propagate_fix(graph, "doc-summarizer", "1.1.0")
        self.assertEqual(states[("doc-summarizer", "1.1.0")]["state"], "current")
        self.assertEqual(states[("new-copy", "1.1.0")]["state"], "current")
        self.assertEqual(check_before_load(graph, ("new-copy", "1.1.0"), states), "allow")


class TestHashing(unittest.TestCase):
    def test_line_endings_do_not_change_hash(self):
        self.assertEqual(hash_skill_text("a\nb\n"), hash_skill_text("a\r\nb\r\n"))

    def test_different_content_changes_hash(self):
        self.assertNotEqual(hash_skill_text("a\n"), hash_skill_text("b\n"))


if __name__ == "__main__":
    unittest.main()
