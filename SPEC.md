# Skill Derivation Graph — Specification v0.1 (Draft)

**Author:** Venkata M Sangaraju, Sr. Database Engineer
**Status:** Draft v0.1, 24 October 2026 — for comment, not a standard.
**Scope:** Provenance, versioning, and fix propagation for agent skills (SKILL.md-style skill definitions).

> **Note on figures.** The ecosystem figures cited in §1 were checked on 24 October 2026 against arXiv:2610.11169v1 and Anthropic's 22 October 2026 announcement. The 50% verbatim-copy share and the 259,596-repository count are figures that paper cites from the GitSkills dataset; the 11.1% figure measures *changes* to a clone group that reach every copy, of which fixes are a subset. All benchmark metrics in §7 are *proposed* — no measurements are claimed in this draft, and no results are reported.

## 1. The problem

Agent skills — reusable SKILL.md definitions that teach an agent how to do a task — have become a supply chain with no supply-chain machinery. Skills are copied freely between repositories, projects, and agent harnesses, but a copy carries no record of where it came from, which version it is a copy of, or whether the source has since been fixed.

"Skill Constellations: Tracing the Supply Chain of Agent Skills on GitHub" (Seddik, UBC Okanagan, arXiv:2610.11169, 8 October 2026) reconstructs a dated copy network covering 2,193,119 skill adoptions. Citing the GitSkills dataset, it notes that the SKILL.md format appeared in 259,596 repositories and that half of all SKILL.md files on GitHub are verbatim copies of another file; its own analysis finds that only 11.1% of changes to a clone group reach every copy, and recommends that platforms distribute versioned references instead of copies. In other words, the ecosystem has the copy behaviour of a software supply chain and none of its provenance: a patched skill leaves most of its descendants silently running the vulnerable version, and a consumer loading a skill has no cheap way to ask "is this current, and what is it derived from?"

Anthropic donated Agent Skills to the Agentic AI Foundation (AAIF, Linux Foundation) on 22 October 2026 and proposed a starting roadmap covering versioned releases, a formal proposal process, and security guidance for people who write and install skills. Versioning answers "which release is this?" It does not answer "which skills descend from this one, and are they still carrying the old version?" The paper's own recommendation — versioned references instead of copies — needs exactly this. This spec proposes the missing layer: a derivation graph over skills, a provenance record carried with each skill, and a fix-propagation mechanism that marks descendants stale when a source is patched.

## 2. Goals and non-goals

**Goals.**

1. Make every skill copy attributable: given a skill, a consumer can walk back to its source and enumerate its derivation chain.
2. Make staleness checkable at load time: before an agent loads a skill, it can ask whether the skill is current, stale-vulnerable, or stale-needing-review.
3. Make fix propagation measurable: define metrics (fix reach, time-to-fix, stale-descendant count, fork-detection accuracy) so the ecosystem can report whether patches actually arrive.
4. Stay registry-agnostic: the graph works over skills wherever they live (repositories, registries, harnesses) and does not require a single central registry.

**Non-goals.**

- This spec does not define a skill format, a skill runtime, or a skill marketplace.
- It does not replace versioning; it sits alongside it (§5).
- It does not certify that a skill is safe. Provenance answers "where did this come from and is it current?" — not "is this code trustworthy?" A signed provenance record from an untrusted author is still untrusted.
- It does not assume honest lineage in adversarial settings: a malicious actor can lie about a parent. §9 states the limits.

## 3. The derivation-graph model

The graph has two node types and three edge types.

### 3.1 Nodes

| Node | Meaning | Identity |
|---|---|---|
| `Skill` | A skill as a named, evolving work (e.g. `doc-summarizer`) | Stable skill name/ID, chosen by its author |
| `SkillVersion` | One immutable release of a skill | `(skill_id, version)` plus the content hash in §4 |

A `Skill` is a mutable pointer to its latest `SkillVersion`. A `SkillVersion` is immutable: if the SKILL.md text changes, the version (and its content hash) changes. Consumers pin versions; authors move the pointer.

### 3.2 Edges

All edges are directed from a version to the version it relates to.

| Edge | Meaning | Example |
|---|---|---|
| `DERIVED_FROM` | Version B was copied or adapted from version A | A verbatim copy, or a modified fork, points `DERIVED_FROM` at its parent version |
| `SUPERSEDES` | Version B replaces version A of the same skill | A patch release `1.1.0` `SUPERSEDES` `1.0.0` |
| `PATCHES` | Version B is a security/bug fix for the vulnerability present in version A | A fix release `1.0.1` `PATCHES` the vulnerable `1.0.0` |

A derivation chain is a path of `DERIVED_FROM` edges. The *derivation type* of an edge is recorded on the child version's provenance record (§4): `verbatim` (byte-identical SKILL.md content after normalisation) or `modified` (any other derivation). This distinction drives the propagation semantics in §6: a verbatim descendant of a patched version inherits the vulnerability by construction; a modified descendant may or may not, and therefore needs review rather than an automatic verdict.

### 3.3 Identity

A version is identified by the triple `(skill_id, version, content_hash)`. The `content_hash` is the SHA-256 of the normalised SKILL.md text: line endings normalised to LF, trailing whitespace stripped per line, exactly one trailing newline. Two files with the same normalised text have the same hash and are the same version content, whatever repository they sit in. This makes "is this a verbatim copy?" a hash comparison, not a judgement call.

## 4. Provenance record schema

Every `SkillVersion` carries one provenance record. The record is small, JSON-serialisable, and designed to travel with the skill (embedded in the skill package, or published alongside it).

| Field | Type | Required | Meaning |
|---|---|---|---|
| `skill_id` | string | yes | Stable skill name/ID |
| `version` | string | yes | Release version (semantic versioning, §5) |
| `content_hash` | string | yes | `sha256:` + hex digest of the normalised SKILL.md text (§3.3) |
| `parent_skill_id` | string \| null | yes | The skill this version was derived from, or `null` for a source skill |
| `parent_version` | string \| null | yes | The parent version, or `null` for a source skill |
| `derivation` | `verbatim` \| `modified` \| null | yes | `null` for a source skill; otherwise how this version relates to its parent |
| `author` | string | yes | Author identity: a public identifier (e.g. a handle, repository owner, or key fingerprint). Free text is accepted; verification is out of scope for v0.1 |
| `signature` | string \| null | no | Optional signature over `content_hash` + `parent` fields, by the author's key. Presence is recorded; verification is left to consumers |
| `created_at` | string (ISO 8601) | yes | When this version was published |
| `supersedes` | string \| null | no | Previous version of the same skill this version replaces |
| `patches` | string \| null | no | Version this version fixes, if it is a fix release |

Example (abridged):

```json
{
  "skill_id": "doc-summarizer",
  "version": "1.0.0",
  "content_hash": "sha256:…",
  "parent_skill_id": null,
  "parent_version": null,
  "derivation": null,
  "author": "alice@example.dev",
  "signature": null,
  "created_at": "2026-10-01T00:00:00Z",
  "supersedes": null,
  "patches": null
}
```

A provenance record with a missing parent, a parent that does not resolve, or a `content_hash` that does not match the SKILL.md text is *unresolved*, not invalid: consumers must treat it as unattributed (see §6.4) rather than rejecting the skill outright, so that adoption is not blocked by incomplete metadata during migration.

## 5. Versioning rule

Two identifiers, two jobs — do not conflate them:

1. **Content-hash identity** answers "is this the same content?" Two versions with the same hash are the same content. This is the identity used for verbatim-copy detection and for the propagation walk.
2. **Semantic version for releases** answers "is this newer, and is it a fix?" Authors release versions as `MAJOR.MINOR.PATCH`. A `PATCH` release that fixes a vulnerability must set `patches` to the vulnerable version (§4) and the release notes must say so. A `MINOR`/`MAJOR` release that also contains the fix sets `patches` as well — the fix marker, not the version bump size, is what the propagation walk keys on.

Rules:

- A version's `content_hash` must never be reused for different content. If content changes, the version changes.
- A fix release must be published as a new version of the *same* skill, so that `SUPERSEDES`/`PATCHES` edges connect it to the vulnerable version. Publishing a fix under a new skill name breaks the propagation chain by design and must not be done silently.
- Pre-release versions (`1.1.0-rc.1`) are versions like any other; consumers pinning stable releases ignore them unless they opt in.

## 6. Fix-propagation mechanism

### 6.1 The patch event

A patch event is: source skill S publishes version V' with `patches = V` (V the vulnerable version). The propagation walk starts at V and follows `DERIVED_FROM` edges *forward* — from parent to children, transitively — over the graph as known to the consumer (a local index, a registry, or a harvested corpus).

### 6.2 Descendant states

After a patch event, each descendant version is in exactly one state:

| State | Condition | Consumer action |
|---|---|---|
| `current` | The version is V' itself, or a version derived from V' | Load normally |
| `superseded` | The version is a pre-patch version of the patched skill itself (V, replaced by V') | Warn: a newer version exists; load only if the old version is deliberately pinned |
| `stale-vulnerable` | The version descends from V through only `verbatim` edges, and has not been updated | **Block by default** (or warn loudly, per consumer policy); the vulnerability is inherited by construction |
| `stale-review` | The version descends from V through at least one `modified` edge | **Warn and require review**: the patch may or may not apply; a human or a diff check decides |
| `unaffected` | The version does not descend from V | Load normally |
| `unresolved` | Provenance is missing or does not resolve (§4) | Load with an "unattributed" warning; do not claim currency |

The walk is a breadth-first traversal from V over child edges, carrying a flag for whether any `modified` edge has been crossed on the path. Distance in hops is recorded per descendant; it feeds the time-to-fix metric (§7).

### 6.3 What the source author must do

1. Publish the fix as a new version of the same skill, with `patches` set (§5).
2. Publish (or update) the derivation index entry so children are discoverable — at minimum, the fix release's provenance record. The walk can only reach descendants the consumer can see; undiscoverable copies are counted as unreached, not as safe (§7).
3. State in the release notes which versions are vulnerable and whether the fix is a drop-in replacement (verbatim descendants can adopt it mechanically) or behaviour-changing (modified descendants need review).

### 6.4 What the consumer must do

Before loading a skill version, the consumer checks its state (§6.2) against the latest known patch events for its ancestors. A consumer that cannot reach a derivation index must say so ("staleness unknown") rather than reporting the skill as current. Staleness is a property of the version *relative to the index the consumer consulted*; the index name and query time belong in any report.

## 7. Benchmark definition (proposed metrics, no results claimed)

The benchmark measures whether patches actually reach descendants. It is defined here so that implementations can be compared; **no measurements exist yet under this spec, and none are claimed.**

### 7.1 Metrics

| Metric | Definition |
|---|---|
| Fix reach % | Share of known descendants of a vulnerable version that have moved to a `current` state within the observation window |
| Time-to-fix (descendants) | For each descendant that updates, elapsed time from patch publication to the descendant's update; reported as median and 90th percentile across descendants, and as median by hop distance from the source |
| Stale-descendant count | Number of descendants still in `stale-vulnerable` or `stale-review` at the end of the observation window, split by state |
| Fork-detection accuracy | On a labelled corpus, precision/recall of classifying a skill as a descendant of a given source (verbatim by hash; modified by provenance + content similarity), against ground-truth derivation labels |
| Unresolved share | Share of harvested skills whose provenance is missing or does not resolve — a migration-health metric, not a security verdict |

### 7.2 Synthetic-corpus evaluation protocol

Because harvesting a live corpus is slow and non-reproducible, v0.1 evaluation uses a synthetic corpus (no real skills, no real authors, no employer data):

1. **Generate** a corpus of synthetic skills with a known ground-truth derivation graph: a mix of source skills, verbatim copies (1–3 hops deep), modified forks, and unrelated skills. Include patch events with known publication times and a mix of adopting, slow, and never-updating descendants.
2. **Run** the reference implementation's propagation walk (§6) over the corpus from each patch event.
3. **Score** the metrics in §7.1 against ground truth. Fork-detection accuracy is scored only on the labelled modified forks.
4. **Report** per-metric results with the corpus parameters (graph size, verbatim/modified mix, adoption-rate distribution, observation window) so that results are comparable across implementations. A result without its corpus parameters is not a result under this spec.
5. **Ablate**: report the same metrics with the derivation graph *removed* (hash-only matching, no parent pointers) to show what the graph adds over content hashing alone. This is the key control: if the graph adds nothing, the spec has failed.

### 7.3 What "good" looks like (targets, not claims)

Targets for a mature implementation, to be revised once baseline measurements exist: fix reach above 80% within 30 days for verbatim descendants; stale-vulnerable count trending to zero for high-severity patches; unresolved share below 10% in a harvested corpus. These are aspirations for the ecosystem, not measurements of any existing system.

## 8. Relationship to AAIF Agent Skills governance

This spec proposes a *provenance layer* to sit alongside the AAIF Agent Skills governance work — versioning, proposal process, and security guidance — not a competing registry, format, or governance body. Concretely: AAIF versioning gives each skill release a stable version; this spec's provenance record references those versions and adds the parent pointers and content hashes that make derivation walkable. A future AAIF proposal could adopt the provenance record as an optional field on a skill release, and a future AAIF index could serve the derivation edges the propagation walk consumes. Nothing in this spec requires AAIF adoption to be useful locally: a team can run the graph over its own skill corpus today.

## 9. Security considerations and limitations

- **Lying about parents.** A malicious author can claim a reputable parent. The graph records claims; it does not verify them. Consumers should weight provenance by author trust (signatures, repository history) and treat unattributed or newly-seen authors accordingly.
- **Signatures are optional in v0.1.** A signature field exists (§4) but no key-management or verification scheme is specified. Do not treat a present-but-unverified signature as trust.
- **Modified forks are judgement calls.** `stale-review` is deliberately not a verdict: only a diff or a human can say whether a patch applies to a fork. Implementations must not silently upgrade `stale-review` to `current`.
- **Coverage is bounded by the index.** Descendants invisible to the consumer's index are unreached, not safe. Reports must name the index and its coverage.
- **Privacy.** Provenance records contain author identifiers by design; authors who need anonymity should use a stable pseudonymous identifier rather than a personal one.

## 10. Roadmap

- **v0.1 (this draft):** model, provenance record, propagation semantics, benchmark definition, reference implementation, synthetic-corpus protocol.
- **v0.2:** signature verification scheme; a harvesting protocol for building a derivation index from public repositories; a `stale-review` diff assistant (does the patch apply cleanly to this fork?).
- **v1.0:** frozen record format; an AAIF proposal for adopting the provenance record as an optional release field; first measured baseline on a harvested corpus, reported with corpus parameters per §7.2.

---

*Venkata M Sangaraju is a Sr. Database Engineer working on governed conversational analytics and agent memory governance, and the author of "Lineage-Aware Memory Governance" (IEEE Access, 2026). Comments and corrections welcome — this draft is intended to start a discussion, not end one.*
