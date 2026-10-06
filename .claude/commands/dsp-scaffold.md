# /dsp:scaffold -- FSI-DSP Artifact Scaffold via Upstream Skill

You orchestrate the scaffolding of a canon-compliant fsi-dsp artifact using one of the upstream skills from `streaming-skills-plugin` (installed and pinned via H.3a + H.3b). The scaffolded output is registered as a proposed fsi-dsp MANIFEST.yaml capability entry with full provenance (operator, profile, canon-stack hash, timestamp, upstream-skill version).

Profile gating, canon-family gating, and activity logging are MANDATORY. You NEVER scaffold under `read-only`. You NEVER scaffold a prod-canon artifact under a developer-family profile.

## Input

$ARGUMENTS

## Step 1: Parse arguments

Parse `$ARGUMENTS`:

- Extract `<artifact-type>` (required, first positional) -- one of `{producer, consumer, kafka-streams-app, schema, cdc-pipeline}`.
- Extract `<name>` (required, second positional) -- kebab-case identifier.
- Extract `--profile <name>` (optional, default `read-only`) -- `read-only`, `engineer`, `break-glass`, `developer/sandbox`.
- Extract `--overlay <customer>` (optional) -- customer overlay for canon stack (e.g., `acme-bank`).
- Extract `--operator <id>` (optional, default `unknown`) -- operator identifier for provenance.
- Extract `--prod` (optional flag) -- explicit declaration that the artifact targets the prod canon stack. Required for production scaffolding under operator-family profiles. REJECTED under developer-family profiles (cross-family canon refusal).
- Extract `--dry-run` (optional flag) -- show what would be scaffolded without writing files.

Validation errors (stop immediately):

- If `<artifact-type>` is missing or not in the valid set: `Error: unknown artifact-type. Valid: cdc-pipeline, consumer, kafka-streams-app, producer, schema`.
- If `<name>` is missing: `Error: name required. Usage: /dsp:scaffold <artifact-type> <name> [--profile <name>]`.
- If `--profile <name>` not recognized by VALID_PROFILES: `Error: unknown profile <name>`.

## Step 2: Invoke the scaffold engine

Delegate to `tools/scaffold_engine.py`:

```bash
python tools/scaffold_engine.py <artifact-type> <name> --profile <name> [--overlay <customer>] [--operator <id>] [--prod] [--dry-run]
```

The engine runs three gates in order -- skill blocklist, read-only operator, cross-family canon -- and either:

- Generates the output directory `outputs/scaffolded/<artifact-type>-<name>-<timestamp>/` containing `manifest-entry.yaml`, `provenance.json`, `scaffold/`, `README.md`. Exit 0.
- Refuses with `blocked-by-profile` (exit 10).
- Refuses with `blocked-by-canon-family` (exit 11).
- Stubs with `not-implemented` for artifact types other than `producer` in H.3c (exit 20).

Every invocation appends an entry to `wiki/activity/YYYY-MM.md` per ACTA-04 schema.

## Step 3: Report results

- On success: print the output directory path; instruct the operator to review `manifest-entry.yaml`, then open a PR against `goodlabs-studio/fsi-dsp` to register the entry.
- On `blocked-by-profile`: explain which gate fired; suggest the right profile.
- On `blocked-by-canon-family`: explain the cross-family refusal; suggest omitting `--prod` or switching to an operator profile.
- On `not-implemented`: note the artifact-type is a H.3c follow-up; suggest the manual upstream-skill invocation.

## Examples

```
/dsp:scaffold producer my-payments-producer --profile developer/sandbox --operator <your-id>
/dsp:scaffold producer my-payments-producer --profile engineer --prod --operator <your-id>
/dsp:scaffold producer my-payments-producer --profile read-only      # blocked
/dsp:scaffold producer my-payments-producer --profile developer/sandbox --prod   # blocked (cross-family)
```

## Rules

- NEVER scaffold under `--profile read-only` -- the skill_blocklist + empty allowed_operations defense in depth blocks both gates.
- NEVER scaffold a prod-canon artifact under a developer-family profile -- cross-family canon refusal.
- ALWAYS read provenance.json + manifest-entry.yaml before opening the fsi-dsp PR.
- Output is a PROPOSAL -- the MANIFEST entry must be reviewed and merged via a PR against `goodlabs-studio/fsi-dsp`; cflt-ai does NOT auto-edit the submodule.
- Only `producer` is end-to-end in H.3c; other artifact types stub with `## TODO: H.3c follow-up` markers.
- Activity log entries follow the `/dsp:apply` ACTA-04 schema; reproducible audit trail for every scaffold invocation (success, blocked, not-implemented).
