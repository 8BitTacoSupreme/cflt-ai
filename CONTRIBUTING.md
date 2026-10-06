# Contributing to cflt-ai

cflt-ai is a shared Confluent knowledge base powered by Claude Code. Contributions flow through PRs — anyone can add wiki articles, run evaluations, and submit discoveries.

## Getting Started

```bash
git clone <repo-url> cflt-ai && cd cflt-ai
flox activate   # optional — see note below
bin/setup
claude
```

See [README.md](README.md) for full setup instructions.

> **Flox is optional.** It only pins the toolchain (Python 3.11, Node, `uv`) for reproducibility. With Python 3.11+ and Node 20+ already on your `PATH`, skip `flox activate` — the setup script and skills behave identically.

## Adding Wiki Articles

### Option A: Manual authoring

1. Create a branch: `git checkout -b wiki/your-topic`
2. Add your article to `wiki/concepts/` or `wiki/patterns/`
3. Follow the format in `.claude/commands/wiki/references/article-format.md`
4. Required frontmatter: `title`, `confidence`, `tags`, `sources`, `last_validated`
5. Register in `wiki/_index.md` and add backlinks to `wiki/_graph.md`
6. Run `/wiki:lint` to check for errors
7. Open a PR

### Option B: From raw sources

1. Add source material (URLs, docs, notes) to `raw/` and register in `raw/_ingest.md`
2. Run `/wiki:ingest` — Claude compiles sources into wiki articles with MCP validation
3. Review the generated articles, then commit and PR

### Option C: From /ask discoveries

While using `/ask`, if you discover something the wiki doesn't cover:
1. Run `/wiki:recommend` with the topic
2. Claude will draft, validate, and write the article
3. Review the output, commit, and PR

## Article Quality Standards

See `.claude/commands/wiki/references/quality-standards.md` for the full spec. Key points:

- **Confidence levels**: `high` (MCP-validated), `medium` (single-source or training data), `low` (unverified or community-sourced)
- **Sources**: Every claim needs a source. Prefer Confluent docs over blog posts.
- **Cross-links**: Articles should link to related concepts and patterns
- **Freshness**: Articles should include `last_validated` date; re-validate quarterly

## Running Skills

| Skill | Purpose | Output |
|-------|---------|--------|
| `/ask` | Quick validated answer | In-conversation |
| `/review` | Evaluate a document | `outputs/reports/<slug>-review-<date>.md` |
| `/wiki:ingest` | Compile raw sources into wiki articles | Wiki articles |
| `/wiki:validate` | Check wiki against live sources | Patches to wiki articles |
| `/wiki:recommend` | Answer + write back discoveries | Wiki articles |
| `/wiki:lint` | Health check | Console output |

## Modifying MANIFEST.yaml

`raw/repos/fsi-dsp/MANIFEST.yaml` is the stable contract between fsi-dsp and cflt-ai.
Before adding entries or types, read [`tools/manifest-schema.md`](tools/manifest-schema.md)
for the full schema reference (top-level fields, base capability fields, all 8 known types,
and the per-type required field tables).

Validate locally with:

```bash
python3 tools/check_manifest.py        # fast schema-only validation
pytest tests/test_manifest.py          # full suite: schema + path existence + expected IDs
```

Adding a new type requires lock-step changes in both repos AND the validator + tests +
schema doc — see the "Adding a new type" runbook in
[`tools/manifest-schema.md`](tools/manifest-schema.md#adding-a-new-type).

## Canon Overlays & Client Silos

The canon stack resolves `base > industry > customer > engagement` (deep merge, later
layer wins; see `canon/stack.py`). Two confidentiality tiers:

- **Shareable canon** — `canon/base/` and `canon/industry/<name>/` (e.g. `fsi`, `retail`)
  are IP committed to this repo. A new industry is just a new directory under
  `canon/industry/` modeled on `fsi/`; select it with
  `resolve_stack(canon_layer="industry/<name>")`. Operators choose the industry per
  scaffold via `dsp-scaffold --industry <name>` (or an `industry` field in their
  operator profile); it defaults to `fsi`. `--prod` targets `industry/<name>`,
  otherwise the industry's `developer-sandbox` tier. The selection is recorded as
  `canon_layer` in each scaffold's `provenance.json`.
- **Client-confidential canon** — `customer/<client>` and `engagement/<name>` overlays
  must **never** be committed here. They live in a **private overlay repo** loaded at
  resolve time.

### Working with a client silo

1. Create a private repo whose paths mirror the canon layers, e.g.:
   ```
   ~/clients/examplebank-canon/
     customer/examplebank/overrides.yaml          # only keys that differ; each cites an ADR
     customer/examplebank/adrs/adr-001.md
     customer/examplebank/profiles/engineer.json  # optional per-client profiles
     engagement/examplebank-2026-payments/overrides.yaml
   ```
   (Model the contents on the committed `canon/customer/acme-bank/` demo.)
2. Point the stack at it: `export CFLT_CANON_EXTERNAL_PATH=~/clients/examplebank-canon`
   (os-pathsep list; `~` expanded). Repo-internal canon is always searched first, so
   external roots cannot shadow shared IP.
3. Resolve: `resolve_stack(customer="examplebank", engagement="examplebank-2026-payments")`.

The shared floor bundle (`tools/canon_preload.py`) only globs the repo's `canon/` —
client overlays enter context **only** via an explicit `resolve_stack` selection,
never the always-on prompt prefix.

### Guardrails (install once)

```bash
git config core.hooksPath .githooks   # enables .githooks/pre-push silo guard
chmod +x .githooks/pre-push
```

`.gitignore` keeps `canon/customer/*` and `canon/engagement/*` untracked (except the
acme-bank demo + scaffolds); the pre-push hook and the `canon-silo-guard.yml` CI job
reject any client/engagement canon that slips into a commit.

### Promoting a pattern up (the "cleanser")

To lift a generalized override from a client silo into shareable canon, scrubbing
client identifiers:

```bash
python3 tools/promote-canon.py --from customer/examplebank --to industry/fsi --scrub examplebank,acct-id
```

It writes a **paste-safe** candidate + diff to `outputs/promote/` (never into
`canon/`), rewrites source citations to `TODO: ADR-xxx`, and reports `NOT READY`
until you fill the target-layer ADRs. Review, add the ADR, then hand-apply.

## PR Guidelines

- Use the PR template (auto-populated)
- CI runs `wiki-lint.py --full` on any PR touching `wiki/`
- Note which claims were MCP-validated in the PR description
- Keep PRs focused: one topic per PR when possible

## Code of Contribution

- Accuracy over volume. One well-validated article beats five unverified ones.
- When in doubt, mark confidence as `medium` and note what needs verification.
- Don't remove content without explanation. If something is wrong, correct it with sources.
- Canon defaults in CLAUDE.md are authoritative unless explicitly overridden with justification.
