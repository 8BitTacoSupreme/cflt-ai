# cflt-ai — Confluent Operational & Knowledge Agent

A Confluent operational and knowledge agent for FSI engagements, built as Claude Code skills against a compounding wiki of validated canon. Three skills serve the engagement lifecycle: `/ask` for peer-level answers, `/review` for customer deliverables, and `/dsp:plan` + `/dsp:apply` for canon-compliant infrastructure operations through a four-gate act rail.

No custom application code. The "app" is Claude Code itself, configured via committed files.

## Quick Start

```bash
# 1. Clone (--recurse-submodules pulls fsi-dsp if you have access)
git clone --recurse-submodules git@github.com:goodlabs-studio/cflt-ai.git && cd cflt-ai

# 2. (Optional) Activate the Flox environment (installs Python, Node.js, etc.)
flox activate

# 3. Run first-time setup (auth, credentials, MCP config)
bin/setup

# 4. Start Claude Code
claude
```

That's it. Ask a question, paste a config, or run a skill.

> **Flox is optional.** It's a convenience wrapper that pins the toolchain (Python 3.11, Node, `uv`) so the wiki/canon tooling is reproducible. If you already have Python 3.11+ and Node 20+ on your `PATH`, skip step 2 — `bin/setup` and the skills run the same. Flox is never required for the [desktop app](#desktop-app-no-flox-required).

### Desktop app (no Flox required)

The Electron app in `app/` is a self-contained front-end over the same skills and is **not** gated on Flox or `bin/setup` — it only needs Node.js ≥ 20 and `pnpm`. To run it in dev:

```bash
git clone --recurse-submodules git@github.com:goodlabs-studio/cflt-ai.git
cd cflt-ai/app
pnpm install
pnpm dev
```

The app shells out to your existing `claude` CLI, so Claude Code still needs to be installed and authenticated (`claude login`). Flox is only required for the Python-based canon tooling and the full CLI workflow above — not for building or running the app.

## What You Can Do

### `/ask` — Get a validated answer

Paste a config snippet, error message, or architecture question. Claude searches the wiki, applies Confluent Canon defaults, and validates claims against live MCP sources. A triage classifier routes queries through wiki-only, wiki+MCP, or deep reasoning paths.

```
/ask What's the right acks setting for a transactional producer writing to a compacted topic?
```

Modes: `--mode ephemeral` (quick answer), `--mode report` (structured output), `--mode reconsolidate` (answer + write back to wiki). `/wiki:recommend` is an alias for `--mode reconsolidate`.

### `/review` — Evaluate a document

Point at a file and get a structured review with deterministic claim extraction, premise-challenge validation, and provenance-stamped output.

```
/review my-dr-proposal.md
```

Supports multi-document input (deck + tfvars + runbook as a single scope), customer overlays for differential canon, and `.docx` export with full provenance footer.

Output lands in `outputs/reports/<slug>-review-<date>.md`.

### `/dsp:plan` — Plan infrastructure changes (read-only)

Plan a Confluent infrastructure change through the four-gate validation chain. The agent selects an existing fsi-dsp artifact (never generates inline Terraform) and validates it against canon compliance, fsi-dsp coverage, confluent-docs schema, and mcp-confluent state.

```
/dsp:plan Create a compacted topic for customer events with Schema Registry
```

### `/dsp:apply` — Execute changes (human-gated)

Execute a planned change with mandatory human confirmation. Three policy profiles enforce least-privilege:

| Profile | Scope | Use Case |
|---------|-------|----------|
| `read-only` | Inspect only | Default for assessments |
| `engineer` | Create/modify within guardrails | Day-to-day operations |
| `break-glass` | Full access, two-step confirmation | Incident response |

Every apply is logged with full provenance and generates a wiki incident entry. 81 mcp-confluent tools are explicitly classified per profile — unclassified tools fail closed.

### Wiki Skills

| Skill | Purpose |
|-------|---------|
| `/wiki:ingest` | Compile raw sources into wiki articles with MCP validation |
| `/wiki:validate` | Check wiki claims against live Confluent docs, patch drift |
| `/wiki:recommend` | Answer questions using wiki + MCP, write back discoveries |
| `/wiki:lint` | Health check: stubs, broken links, orphans, stale articles |
| `/wiki:evaluate` | Full evaluation of external documents against wiki + MCP |

### CLI Tools

```bash
wiki-search "cluster linking DR"    # full-text search
wiki-lint --full                     # health check (includes decay audit)
wiki-stats                           # coverage metrics
wiki-compile --delta                 # process raw ingest queue
```

## Project Structure

```
cflt-ai/
├── .mcp.json                        # MCP server declarations
├── CLAUDE.md                        # Confluent Canon (auto-read by Claude Code)
├── .claude/
│   ├── settings.json                # Shared permission allowlist
│   ├── settings.local.json          # Personal overrides (gitignored)
│   └── commands/
│       ├── ask.md                   # /ask skill
│       ├── review.md                # /review skill
│       ├── dsp-plan.md              # /dsp:plan skill (act rail — plan)
│       ├── dsp-apply.md             # /dsp:apply skill (act rail — apply)
│       └── wiki/                    # Wiki skills (ingest, validate, etc.)
├── canon/                           # Four-layer overlay stack
│   ├── stack.py                     # Stack resolution engine
│   ├── base/defaults.yaml           # GoodLabs canonical defaults
│   ├── industry/fsi/overrides.yaml  # FSI-specific overrides
│   ├── customer/acme-bank/          # Customer overlay (demo)
│   │   ├── overrides.yaml
│   │   └── profiles/engineer.json   # Customer-specific profile gating
│   └── engagement/                  # Per-engagement overrides
├── wiki/
│   ├── _index.md                    # Master article index
│   ├── _graph.md                    # Backlink registry
│   ├── _queue.md                    # Auto-stub work queue
│   ├── activity/                    # Per-overlay activity logs
│   ├── incidents/                   # Apply incident entries
│   ├── concepts/                    # Foundational knowledge (11 articles)
│   ├── patterns/                    # Reusable architecture patterns (8 articles)
│   └── synthesis/                   # Cross-cutting analysis, ADR index
├── tools/                           # Python CLI tools + act rail engine
│   ├── act_gates.py                 # Four-gate validation chain
│   ├── apply_engine.py              # Apply execution with profile gating
│   ├── review-to-docx.py            # .docx export with provenance footer
│   ├── check-canon-parity.py        # Canon ↔ fsi-dsp drift detector
│   ├── check-citations.py           # Wiki citation resolver
│   ├── wiki-lint.py                 # Wiki linter with decay audit
│   ├── wiki-compile.py              # Raw source compiler
│   ├── wiki-search.py               # Full-text wiki search
│   ├── wiki-stats.py                # Coverage metrics
│   └── profiles/                    # Policy profile definitions
│       ├── read-only.json
│       ├── engineer.json
│       ├── break-glass.json
│       └── tool_classification.json # 81 mcp-confluent tools classified
├── tests/                           # Golden test harnesses + unit tests
│   ├── golden/ask/                  # 40+ /ask test cases
│   ├── golden/act/                  # 30+ /dsp:plan and /dsp:apply cases
│   ├── test_act_gates.py            # Four-gate unit tests
│   ├── test_apply_engine.py         # Apply engine + profile gating tests
│   ├── test_profile_gating.py       # Per-tool negative-space suites
│   └── ...                          # Canon overlay, citation, decay tests
├── raw/
│   └── repos/fsi-dsp/              # Git submodule: Terraform, Ansible, ADRs
├── outputs/                         # Generated reports and .docx files
├── bin/
│   └── setup                        # First-run setup script
└── .github/
    └── workflows/
        ├── wiki-lint.yml            # CI lint for wiki PRs
        ├── canon-parity.yml         # Canon ↔ fsi-dsp drift CI
        └── manifest-citations.yml   # Citation resolution CI
```

## How It Works

```mermaid
graph TD
    CC["Claude Code<br/>(runtime host)"]

    CC --> ASK["/ask"]
    CC --> REV["/review"]
    CC --> PLAN["/dsp:plan"]
    CC --> APPLY["/dsp:apply"]
    CC --> WS["Wiki Skills<br/>ingest · validate · lint · evaluate"]

    subgraph sources["Knowledge Sources"]
        WIKI["Wiki<br/>20 articles<br/>concepts + patterns + synthesis"]
        CANON["Canon Overlay Stack<br/>base → FSI → customer → engagement<br/><i>stack.py resolves layers</i>"]
        MCP["MCP Servers<br/>context7 · confluent-docs · mcp-confluent"]
    end

    ASK --> WIKI & CANON & MCP
    REV --> WIKI & CANON & MCP
    WS --> WIKI & MCP

    subgraph actrail["Act Rail Engine"]
        GATES["act_gates.py<br/>Gate 1: Canon compliance<br/>Gate 2: fsi-dsp coverage<br/>Gate 3: confluent-docs schema<br/>Gate 4: mcp-confluent state"]
        ENGINE["apply_engine.py<br/>Profile enforcement<br/>Tool classification check"]
        PROFILES["Policy Profiles<br/>read-only · engineer · break-glass"]
        TOOLCLASS["tool_classification.json<br/>81 mcp-confluent tools<br/>classified by profile tier"]
    end

    PLAN --> GATES
    APPLY --> ENGINE --> GATES
    ENGINE --> PROFILES & TOOLCLASS
    GATES --> CANON & MCP

    subgraph artifacts["fsi-dsp Artifact Library"]
        MANIFEST["MANIFEST.yaml<br/>Stable IDs · capabilities blocks"]
        TF["Terraform Modules"]
        ANSIBLE["Ansible Roles"]
        ADRS["ADRs + Ref Code"]
    end

    GATES --> MANIFEST
    MANIFEST --- TF & ANSIBLE & ADRS

    subgraph outputs["Outputs"]
        REPORTS["outputs/reports/<br/>Review .md + .docx"]
        PLANS["outputs/plans/<br/>Plan documents"]
        ACTIVITY["wiki/activity/<br/>Per-overlay activity logs"]
        INCIDENTS["wiki/incidents/<br/>Apply incident articles"]
    end

    REV --> REPORTS
    PLAN --> PLANS
    APPLY --> INCIDENTS
    ASK & REV & PLAN & APPLY --> ACTIVITY

    subgraph ci["CI Enforcement"]
        WL["wiki-lint.yml"]
        CP["canon-parity.yml"]
        MC["manifest-citations.yml"]
    end

    WL --> WIKI
    CP --> CANON & MANIFEST
    MC --> WIKI & MANIFEST

    classDef skill fill:#4a90d9,color:#fff,stroke:#2c5f8a
    classDef source fill:#50b86c,color:#fff,stroke:#2d7a42
    classDef engine fill:#e6a23c,color:#fff,stroke:#b8860b
    classDef output fill:#909399,color:#fff,stroke:#606266
    classDef cinode fill:#f56c6c,color:#fff,stroke:#c0392b

    class ASK,REV,PLAN,APPLY,WS skill
    class WIKI,CANON,MCP source
    class GATES,ENGINE,PROFILES,TOOLCLASS engine
    class REPORTS,PLANS,ACTIVITY,INCIDENTS output
    class WL,CP,MC cinode
```

**Skills** combine these sources: the wiki provides institutional knowledge, the canon overlay stack provides layered defaults (base → industry → customer → engagement), MCP servers provide live validation, and fsi-dsp provides the artifact library that the act rail operates against.

**The act rail** never generates infrastructure code. It selects existing fsi-dsp artifacts through a four-gate chain (canon compliance → fsi-dsp coverage → schema validation → state check), applies profile-based least-privilege gating, and executes only after explicit human confirmation.

## Skill Flows

```mermaid
flowchart TD
    USER((User))

    USER -->|question or config| ASK_START
    USER -->|document path| REV_START
    USER -->|"/wiki:recommend"| ALIAS
    USER -->|infra request| PLAN_START
    USER -->|"--plan path"| APPLY_START

    ALIAS["/wiki:recommend<br/><i>alias</i>"] -->|"--mode reconsolidate"| ASK_START

    subgraph ask["/ask — Validated Answer"]
        ASK_START["Parse --mode<br/>ephemeral · report · reconsolidate"]
        ASK_START --> TRIAGE["Triage Classifier"]
        TRIAGE -->|"3+ wiki hits,<br/>no version/config keys"| WIKI_ONLY["Wiki-Only Route"]
        TRIAGE -->|"version numbers,<br/>config keys, API names"| WIKI_MCP["Wiki + MCP Route"]
        TRIAGE -->|"multi-topic, design,<br/>trade-off analysis"| DEEP["Deep Route"]
        TRIAGE -->|"off-domain"| REFUSE["Refuse"]

        WIKI_ONLY --> WSEARCH["Search Wiki"]
        WIKI_MCP --> WSEARCH
        DEEP --> WSEARCH

        WSEARCH -->|miss| STUB["Auto-stub → _queue.md"]
        WSEARCH -->|hit| CANON_CHK["Apply Canon Defaults"]
        STUB --> CANON_CHK

        CANON_CHK --> MCP_VAL{"MCP Validate?"}
        MCP_VAL -->|"wiki-only"| MODE
        MCP_VAL -->|"wiki+MCP / deep"| VALIDATE["Validate via<br/>confluent-docs · context7"] --> MODE

        MODE{"--mode?"}
        MODE -->|ephemeral| DISPLAY["Display answer<br/><i>no files written</i>"]
        MODE -->|report| WRITE_RPT["Write report file"]
        MODE -->|reconsolidate| WRITE_RECON["Write report +<br/>Update wiki articles"]
    end

    subgraph review["/review — Document Evaluation"]
        REV_START["Parse --output --overlay<br/>Load documents"]
        REV_START --> EXTRACT["Extract Claims<br/><i>YAML block — 5 categories</i>"]
        EXTRACT --> PREMISE["Premise Challenge<br/><i>3–5 unstated assumptions</i>"]
        PREMISE --> WIKI_XREF["Cross-ref Wiki"]
        WIKI_XREF -->|miss| STUB2["Auto-stub → _queue.md"]
        WIKI_XREF --> MCP_CHK["MCP Validation"]
        STUB2 --> MCP_CHK
        MCP_CHK --> CANON_CMP["Canon Compliance Check"]
        CANON_CMP --> GEN_RPT["Generate Report"]
        GEN_RPT --> OUTPUT{"--output?"}
        OUTPUT -->|md| MD_OUT[".md report"]
        OUTPUT -->|docx| DOCX_OUT[".docx with<br/>provenance footer"]
        OUTPUT -->|both| BOTH_OUT[".md + .docx"]
    end

    subgraph plan["/dsp:plan — Infrastructure Plan"]
        PLAN_START["Parse request +<br/>--overlay --gate-bypass"]
        PLAN_START --> LOAD_CANON["Load Canon Stack"]
        LOAD_CANON --> GATE_CHAIN["Four-Gate Chain"]

        GATE_CHAIN --> G1["Gate 1: Canon Compliance"]
        G1 --> G2["Gate 2: fsi-dsp Coverage"]
        G2 --> G3["Gate 3: confluent-docs Schema"]
        G3 --> G4["Gate 4: mcp-confluent State"]

        G4 -->|all pass| SELECT["Select Artifact +<br/>Build Arguments"]
        G4 -->|any fail| FAIL_PLAN["Failure Report<br/><i>never generates inline TF</i>"]
        SELECT --> WRITE_PLAN["Write Plan Document"]
    end

    subgraph apply["/dsp:apply — Execute Changes"]
        APPLY_START["Parse --plan --profile<br/>--overlay --operator"]
        APPLY_START --> LOAD_PROF["Load Profile"]

        LOAD_PROF -->|read-only| BLOCKED["Blocked<br/><i>no apply operations</i>"]
        LOAD_PROF -->|engineer / break-glass| PARSE_PLAN["Parse Plan File"]

        PARSE_PLAN --> RERUN["Re-run Gate Chain<br/><i>no bypass allowed</i>"]
        RERUN -->|fail| DRIFT["State Drift — Blocked"]
        RERUN -->|pass| PERM_CHK["Profile Permission Check"]

        PERM_CHK -->|denied| PERM_DENY["Operation Not Permitted"]
        PERM_CHK -->|allowed| PROFILE_CHK{"Profile?"}

        PROFILE_CHK -->|engineer| CONFIRM["Human Confirmation<br/>CONFIRM APPLY · CANCEL"]
        PROFILE_CHK -->|break-glass| BG_FLOW["Two-Step Break-Glass"]
        BG_FLOW --> BG1["Step 1: Override Reason"]
        BG1 --> BG2["Step 2: Confirm with Reason"]
        BG2 --> EXEC

        CONFIRM -->|CONFIRM| EXEC["Execute via<br/>fsi-dsp Artifact"]
        CONFIRM -->|CANCEL| CANCELLED["Cancelled"]
        CONFIRM -->|"skip / just do it"| BYPASS_LOG["Bypass Attempt Logged<br/><i>refused</i>"]

        EXEC --> LOG["Activity Log +<br/>Incident Article"]
    end

    classDef start fill:#4a90d9,color:#fff,stroke:#2c5f8a
    classDef decision fill:#e6a23c,color:#fff,stroke:#b8860b
    classDef block fill:#f56c6c,color:#fff,stroke:#c0392b
    classDef output fill:#50b86c,color:#fff,stroke:#2d7a42
    classDef alias fill:#909399,color:#fff,stroke:#606266

    class ASK_START,REV_START,PLAN_START,APPLY_START start
    class TRIAGE,MODE,OUTPUT,MCP_VAL,PROFILE_CHK decision
    class BLOCKED,DRIFT,PERM_DENY,BYPASS_LOG,REFUSE,FAIL_PLAN block
    class DISPLAY,WRITE_RPT,WRITE_RECON,MD_OUT,DOCX_OUT,BOTH_OUT,WRITE_PLAN,LOG output
    class ALIAS alias
```

## Canon Overlay Stack

The canon overlay stack lets customers fork and override safely:

```
base/defaults.yaml          # GoodLabs canonical Confluent defaults
  └─ industry/fsi/          # FSI: latency SLA tiers, exactly-once for reg reporting
      └─ customer/acme-bank/ # Acme Bank: zstd compression, sub-100μs latency floor
          └─ engagement/     # Per-engagement overrides (ephemeral)
```

Each layer overrides the layer above. Every override is an ADR in the layer that introduces it. The active stack hash is recorded in every artifact's provenance footer.

## fsi-dsp Reference Repo (Optional)

The [fsi-dsp](https://github.com/goodlabs-studio/fsi-dsp) repo is linked as a git submodule at `raw/repos/fsi-dsp/`. It contains Terraform modules, Ansible roles, ADRs, and reference implementations. MANIFEST.yaml is the binding contract — cflt-ai cites artifacts by stable ID; CI in both repos enforces ID stability and citation resolution.

`bin/setup` offers to initialize it. You can also do it manually:

```bash
git submodule update --init raw/repos/fsi-dsp
```

Requires SSH access to `goodlabs-studio/fsi-dsp`. Without it, wiki and knowledge skills still work — the act rail (`/dsp:plan`, `/dsp:apply`) requires it.

## Confluent Cloud Integration (Optional)

The `mcp-confluent` server lets Claude query live Confluent Cloud clusters (topics, schemas, Flink SQL). Setup during `bin/setup`, or manually:

```bash
mkdir -p ~/.config/confluent
cat > ~/.config/confluent/mcp.env << 'EOF'
CONFLUENT_CLOUD_API_KEY=<your-key>
CONFLUENT_CLOUD_API_SECRET=<your-secret>
EOF
export CONFLUENT_MCP_ENV_FILE=~/.config/confluent/mcp.env
```

Without CC credentials, the wiki and skills still work — you just can't query live clusters or run gate 4 (state check) of the act rail.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide. The short version:

1. Branch from `main`
2. Add/modify wiki articles, run `/wiki:lint`
3. Open a PR — CI validates wiki structure, citation resolution, and canon parity automatically
4. Note which claims were MCP-validated in the PR description

## Requirements

- **[Flox](https://flox.dev)** — manages the dev environment (Python, Node.js, etc.) for the CLI/skills workflow and canon tooling. **Not required for the desktop app** — that path only needs Node.js ≥ 20 + `pnpm` (see [Desktop app](#desktop-app-no-flox-required)).
- **Claude Code** — installed separately via `npm install -g @anthropic-ai/claude-code` or Homebrew
- **Claude auth** — either a Claude Max/Pro subscription or an Anthropic API key
