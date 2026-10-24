"""CLI: run a fix-propagation walk over a JSON skill graph.

Usage (from the repo root):

    python3 -m skillgraph.cli examples/chain.json \\
        --source doc-summarizer --patched-version 1.1.0

Input JSON shape: {"skills": [<provenance records, SPEC.md §4>]}.
A record may carry "skill_text"; when "content_hash" is null the hash is
computed from it, so the example stays self-verifying. Use --output to
write the outcome JSON to a file.
"""

import argparse
import json
import sys
from pathlib import Path

from .hashing import hash_skill_text
from .model import DerivationGraph, SkillVersion
from .propagation import check_before_load, propagate_fix


def load_graph(path: Path) -> DerivationGraph:
    data = json.loads(path.read_text(encoding="utf-8"))
    graph = DerivationGraph()
    for record in data["skills"]:
        record = dict(record)
        if not record.get("content_hash") and record.get("skill_text"):
            record["content_hash"] = hash_skill_text(record["skill_text"])
        graph.add(SkillVersion.from_dict(record))
    return graph


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Skill Derivation Graph propagation walk")
    parser.add_argument("graph", type=Path, help="JSON skill graph file")
    parser.add_argument("--source", required=True, help="patched skill id")
    parser.add_argument("--patched-version", required=True, help="new fixed version")
    parser.add_argument(
        "--vulnerable-version",
        default=None,
        help="version the patch fixes (V); default: every version of the source below --patched-version",
    )
    parser.add_argument("--output", type=Path, default=None, help="write outcome JSON here")
    args = parser.parse_args(argv)

    graph = load_graph(args.graph)
    states = propagate_fix(graph, args.source, args.patched_version, args.vulnerable_version)
    results = []
    for key in sorted(states):
        entry = states[key]
        results.append(
            {
                "skill_id": key[0],
                "version": key[1],
                "state": entry["state"],
                "hops": entry["hops"],
                "load_decision": check_before_load(graph, key, states),
                "reason": entry["reason"],
            }
        )
    summary: dict[str, int] = {}
    for entry in results:
        summary[entry["state"]] = summary.get(entry["state"], 0) + 1
    outcome = {
        "patch": {"source_skill_id": args.source, "patched_version": args.patched_version},
        "summary": summary,
        "results": results,
    }
    text = json.dumps(outcome, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
