# Skill Derivation Graph

**A provenance layer for agent skills: who copied whom, and who is still running the old version.**

Agent skills (SKILL.md-style definitions) are copied freely across repositories and agent harnesses, but a copy carries no record of where it came from or whether its source has since been patched. "Skill Constellations: Tracing the Supply Chain of Agent Skills on GitHub" (Seddik, UBC Okanagan, arXiv:2610.11169, 8 October 2026) cites the GitSkills dataset finding that half of all SKILL.md files on GitHub are verbatim copies of another file, and reports that only 11.1% of changes to a clone group reach every copy — so a fix to a source skill usually does not arrive downstream. This project proposes the missing layer: a derivation graph over skills, a small provenance record carried with each skill version, and a fix-propagation walk that marks descendants stale when a source is patched.

> Status: draft v0.1 (see `SPEC.md`). Figures cited here were checked against arXiv:2610.11169v1 and Anthropic's 22 October 2026 announcement on 24 October 2026. All benchmark metrics are proposed, not measured — this repo contains no results.

## What it is

- **`SPEC.md`** — the full v0.1 specification: the derivation-graph model, the provenance record schema, the versioning rule, the fix-propagation mechanism, and the benchmark definition.
- **`skillgraph/`** — a minimal, standard-library-only Python reference implementation: content hashing of a SKILL.md file, a small derivation graph, and a fix-propagation walk.
- **`examples/`** — a worked 3-node chain (source → verbatim copy → modified fork) plus the propagation outcome when the source is patched.
- **`tests/`** — unit tests for the propagation walk (standard library `unittest`, no dependencies).

## Folder layout

```
skill-derivation-graph/
├── SPEC.md
├── README.md
├── skillgraph/
│   ├── __init__.py
│   ├── hashing.py       # content hashing of SKILL.md text/files
│   ├── model.py         # SkillVersion + DerivationGraph
│   ├── propagation.py   # fix-propagation walk + load-time check
│   └── cli.py           # run a propagation over an example JSON file
├── examples/
│   ├── chain.json           # 3-node skill chain
│   └── chain-outcome.json   # propagation outcome when the source is patched
└── tests/
    └── test_propagation.py
```

## How to run

From this folder, with Python 3.10+ (standard library only, nothing to install):

```bash
# Run the worked example: patch doc-summarizer to 1.1.0 and see what happens
# to its descendants
python3 -m skillgraph.cli examples/chain.json --source doc-summarizer --patched-version 1.1.0

# Run the tests
python3 -m unittest discover tests -v
```

The propagation walk marks each descendant as `current`, `stale-vulnerable`
(verbatim descendants of the patched version — blocked by default), or
`stale-review` (modified forks — the patch may or may not apply, so a human
or a diff check decides). See `SPEC.md` §6 for the full semantics.

## How it relates to AAIF Agent Skills governance

Anthropic donated Agent Skills to the Agentic AI Foundation (AAIF, Linux
Foundation) on 22 October 2026, and proposed a starting roadmap covering versioned
releases, a formal proposal process, and security guidance. This project is a **provenance layer to sit alongside that work,
not a competing registry**: AAIF versioning gives each skill release a stable
version; this spec's provenance record references those versions and adds the
parent pointers and content hashes that make derivation walkable. A future
AAIF proposal could adopt the provenance record as an optional field on a
skill release, and a future AAIF index could serve the derivation edges the
propagation walk consumes. Nothing here requires AAIF adoption to be useful
locally — a team can run the graph over its own skill corpus today.

## Roadmap

- **v0.1 (this draft):** spec, reference implementation, worked example, synthetic-corpus benchmark definition.
- **v0.2:** signature verification scheme; a harvesting protocol for building a derivation index from public repositories; a diff assistant for `stale-review` forks (does the patch apply cleanly?).
- **v1.0:** frozen record format; an AAIF proposal for the provenance record as an optional release field; first measured baseline on a harvested corpus.

## Notes

- All example data is synthetic. No real skills, authors, or organisations are represented.
- The reference implementation is intentionally small: it demonstrates the semantics, it is not a production index. A production deployment needs a real derivation index, key management for signatures, and the harvesting protocol planned for v0.2.
