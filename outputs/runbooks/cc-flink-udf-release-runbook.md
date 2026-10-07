---
title: "Confluent Cloud Flink — UDF Release and SQL Registration"
type: runbook
scope: JFrog Artifactory → Confluent Cloud Flink artifact → CREATE FUNCTION → dependent statement migration, via Terraform + CI/CD on Azure
audience: platform engineering / streaming CoE
created: 2026-09-09
supersedes: prior draft (in-place statement update — does not work; see §0)
validated_against:
  - confluent-docs MCP 2026-09-09 (flink/how-to-guides/create-udf)
  - Terraform registry, confluentinc/confluent 2.85.0
  - raw/repos/fsi-dsp modules/flink, reference/flink-sql
status: ready-to-execute
---

# Runbook — Confluent Cloud Flink UDF Release

Releasing a new or updated UDF from JFrog Artifactory into Confluent Cloud, and migrating the SQL statements that consume it, via Terraform + CI/CD on Azure.

---

## 0. What changed from the previous draft

Three corrections, all load-bearing. If you have the earlier version in a repo, replace it.

| # | Previous draft said | Reality |
|---|---|---|
| 1 | Consuming statements migrate via a normal `terraform apply` — *"not a resource recreation"* | **False.** `statement` is not an editable attribute. Migration requires `terraform apply -replace=`. Confluent: *"You can't swap the UDF underneath a running or stopped statement in place."* |
| 2 | `confluent_flink_statement` needs only `CONFLUENT_CLOUD_API_KEY`/`SECRET` | **Incomplete.** Statements require a `credentials` block holding a **Flink API key**, which is region-scoped and distinct from the Cloud API key. Artifact upload works without it; statement creation does not. |
| 3 | Dropping a function breaks *running* statements | **Inverted.** *"Currently running statements are unaffected."* The damage lands on **stopped and failed** statements, whose compiled plans pin the old artifact. They fail on resume, not at drop time. |

A fourth interaction nobody caught: **`prevent_destroy = true` blocks the replacement that correction 1 requires.** See §6.

---

## 1. Preconditions

- [ ] Confluent Cloud **service account** (not a user account) for statement execution — `fsi-dsp` pitfall 6
- [ ] Least-privilege RBAC, per `wiki/concepts/flink-confluent-cloud-setup.md:59-69` — `EnvironmentAdmin` is **not** required:

  | Role | Grants | Use for |
  |---|---|---|
  | `FlinkFunctionDeveloper` | Manage UDF artifacts and external connectivity. **No statement or compute pool access.** | The CI identity that runs §5 (artifact upload) only |
  | `FlinkDeveloper` | Create/run statements, manage own workspaces, manage UDF artifacts (with cluster access). Granted by default at org/env scope; bind at **compute-pool scope** to restrict to specific pools. | The identity that runs §6–§8 (function registration, statement migration) |

  Splitting these across two CI identities is the FSI-preferred shape: the upload job cannot touch running statements, and the migration job is pool-scoped. Remember Flink RBAC is **control plane only** — the statement's `principal` still needs Kafka/SR data-plane RBAC to read and write topics.
- [ ] **Two** credential pairs in CI, not one:
  - Cloud API key/secret → artifact upload
  - **Flink API key/secret, scoped to the target Flink region** → statement operations
- [ ] JFrog Artifactory repo holding versioned UDF JARs
- [ ] Terraform ≥ 1.5; `confluentinc/confluent` provider — pin it, do not float on `>= 2.x` (current: **2.85.0**)
- [ ] `azurerm` backend for state (Storage Account + container, native blob locking)
- [ ] Flink compute pool already provisioned — not recreated per release
- [ ] JAR built on **Java 11–21**. Java 22+ compiles and uploads fine, then fails at statement runtime

### Provider pin

```hcl
terraform {
  required_providers {
    confluent = {
      source = "confluentinc/confluent"
      # Pin the minor. Statement and artifact resource behaviour has shifted
      # across 2.x; floating on ">= 2.0" makes CI non-reproducible.
      version = "~> 2.85"
    }
  }
}
```

### If your CI uses OIDC federation

Where `principal.id` is a service account rather than an Identity Pool, the Identity Pool needs an `Assigner` role binding on that service account, or statement submission returns **403 Forbidden**:

```hcl
resource "confluent_role_binding" "identity_pool_assigner" {
  principal   = "User:pool-abc123"
  role_name   = "Assigner"
  crn_pattern = "${data.confluent_organization.main.resource_name}/service-account=sa-def456"
}
```

---

## 2. Repo layout

```
repo/
├── udf/fraud-score/                 # Java/Maven module
├── terraform/
│   ├── environments/{dev,staging,prod}/
│   └── modules/
│       ├── flink-artifact/
│       └── flink-statement/
├── sql/fraud_score_pipeline.sql
└── .github/workflows/
    ├── udf-release.yml              # build → JFrog → artifact upload
    └── udf-migrate.yml              # statement replacement — manual gate on prod
```

Keep build/upload separate from statement migration. **They are not the same risk class:** upload is additive and reversible, migration destroys and recreates running jobs.

---

## 3. Build, version, publish to JFrog

Nothing Confluent-specific. One rule: the JAR carries an explicit version, never `latest`.

```bash
set -euo pipefail

mvn versions:set -DnewVersion=2.3.0
mvn clean verify                 # unit tests
mvn deploy                       # → udf-fraudscore/2.3.0/udf-fraudscore-2.3.0.jar
```

Pin the toolchain in `pom.xml` so a runner upgrade can't silently push you past Java 21:

```xml
<properties>
  <!-- CC Flink supports Java 11-21. A JAR built on 22+ uploads successfully
       and then fails at statement runtime, which is a much worse place to
       find out. -->
  <maven.compiler.release>17</maven.compiler.release>
</properties>
```

---

## 4. Resolve the exact JAR in CI

```bash
set -euo pipefail

jf rt download \
  "udf-releases-local/com/goodlabs/udf-fraudscore/2.3.0/udf-fraudscore-2.3.0.jar" \
  ./build/

test -s ./build/udf-fraudscore-2.3.0.jar || { echo "JAR not downloaded"; exit 1; }
```

The `test -s` matters: `jf rt download` can exit 0 having matched nothing.

---

## 5. Upload as a new artifact

Artifacts are immutable and unique per **cloud + region + environment**. Each upload produces a new artifact with its own ID. Never reuse a `display_name`.

```hcl
# terraform/modules/flink-artifact/main.tf

resource "confluent_flink_artifact" "fraud_score_v2_3_0" {
  display_name = "fraud_score_udf_2_3_0"

  # Artifacts support AWS and AZURE only — there is no GCP artifact support.
  # This blocks porting the pattern to the fsi-dsp cc-gcp scenario.
  cloud  = "AZURE"
  region = var.flink_region # must match the compute pool's region

  content_format   = "JAR"
  runtime_language = "Java" # defaults to Java; set explicitly so a Python
                            # UDF added later can't inherit the wrong default
  artifact_file    = "${path.module}/../../../build/udf-fraudscore-2.3.0.jar"
  description      = "Fraud scoring UDF v2.3.0 — see CHANGELOG.md"

  environment {
    id = var.environment_id
  }

  # Deliberately NOT prevent_destroy. The provider recommends it, but artifact
  # retirement (§8) is a planned operation in this workflow and the guard would
  # block it. The protection that matters is ordering: never delete an artifact
  # until §8's reference check passes.
}

output "artifact_id" {
  # Do not assert a prefix. Provider docs show `lfa-`, the import example shows
  # `fa-`, and the CLI emits `cfa-`. Pass the value through, don't validate it.
  value = confluent_flink_artifact.fraud_score_v2_3_0.id
}
```

Note: the `class` attribute is **deprecated** — the class name belongs in `CREATE FUNCTION`, not the artifact.

```bash
set -euo pipefail

terraform apply -target=confluent_flink_artifact.fraud_score_v2_3_0 \
  -var="flink_region=eastus2" \
  -var="environment_id=env-abc123"

ARTIFACT_ID="$(terraform output -raw artifact_id)"
test -n "$ARTIFACT_ID" || { echo "empty artifact_id"; exit 1; }
echo "uploaded artifact: $ARTIFACT_ID"
```

Artifact upload authenticates with the **Cloud** API key. This step will succeed even if your Flink API key is missing or wrong — which is exactly why §6 fails confusingly if you skip the credential setup.

---

## 6. Register the function

Function registration is a `confluent_flink_statement` running `CREATE FUNCTION`.

### Strategy — versioned function names, and why we diverge from the docs

Confluent's documented rollout drops the function and recreates it **under the same name** pointing at the new artifact. **We deliberately do not do that.**

We register `fraud_score_v2` alongside the existing `fraud_score`. The reason is specific to environments with stopped or scheduled statements: because v1 is never dropped during migration, statements pinned to the v1 artifact keep resuming successfully through the whole migration window. The same-name procedure has a window where they cannot.

Record this as a deliberate divergence in your ADR, not an accident.

```hcl
# terraform/modules/flink-statement/function.tf

resource "confluent_flink_statement" "register_fraud_score_v2" {
  organization { id = data.confluent_organization.main.id }
  environment  { id = var.environment_id }
  compute_pool { id = var.compute_pool_id }
  principal    { id = var.flink_service_account_id }

  statement = <<-EOT
    CREATE FUNCTION fraud_score_v2
    AS 'com.goodlabs.udf.FraudScoreFunction'
    USING JAR 'confluent-artifact://${var.artifact_id}';
  EOT

  properties = {
    "sql.current-catalog"  = var.environment_display_name
    "sql.current-database" = var.kafka_cluster_display_name
  }

  # Public networking. For private networking use:
  #   data.confluent_flink_region.main.private_rest_endpoint
  # or:
  #   "https://flink${data.confluent_network.main.endpoint_suffix}"
  rest_endpoint = data.confluent_flink_region.main.rest_endpoint

  # REQUIRED. A Flink API key is region-scoped and is NOT the Cloud API key.
  # Omitting this is the single most common reason this pipeline fails after
  # a successful artifact upload.
  credentials {
    key    = var.flink_api_key
    secret = var.flink_api_secret
  }

  lifecycle {
    prevent_destroy = true
  }
}
```

If a UDF calls an external service, add `USING CONNECTIONS ('my_external_service')` and manage the endpoint with a `confluent_flink_connection` resource rather than embedding secrets in statement properties.

---

## 7. Migrate consuming statements — replacement, not update

> **This is the step the previous draft got wrong.** `statement` is not an editable attribute. The editable set is enumerated by the provider and consists of `stopped`, plus `principal.id` and `compute_pool.id` when resuming a stopped statement. Changing the SQL forces replacement.
>
> Confluent: *"Drop and recreate the statements that use the UDF so that they recompile and bind to the new artifact."*
>
> If you attempt an in-place update anyway, the documented symptom is an `apply` that **hangs on `Still modifying...` and eventually fails with context-deadline-exceeded** — not a clean error.

### 7.1 Pre-flight — enumerate stopped and failed statements

Do this **before** touching anything. Running statements are not the risk; stopped and failed ones are, because their compiled plans pin the old artifact and they fail only on resume.

```bash
set -euo pipefail

# ⚠️ Confirm the JSON shape on your CLI version before wiring this into a gate.
# Dump it raw once and read the field names rather than trusting the paths below:
#   confluent flink statement list --environment "$ENV_ID" --output json | jq '.[0]'

confluent flink statement list \
  --environment "$ENV_ID" \
  --compute-pool "$POOL_ID" \
  --output json \
  | jq -r '.[] | select((.status.phase // .phase // "UNKNOWN") != "RUNNING")
           | "\(.name)\t\(.status.phase // .phase // "UNKNOWN")"'
```

A `jq` path that silently matches nothing returns empty and exits 0 — which reads exactly like "no stopped statements." Verify the filter against a known-stopped statement before trusting an empty result.

Record the output. Every non-`RUNNING` statement that references `fraud_score` needs an explicit decision: migrate it now, or accept it will fail on resume once v1 is retired in §8.

### 7.2 Update the SQL

```hcl
resource "confluent_flink_statement" "fraud_pipeline" {
  # ...same block structure as §6, including credentials...
  statement = <<-EOT
    INSERT INTO scored_transactions
    SELECT
      txn_id,
      fraud_score_v2(txn_payload) AS score   -- was fraud_score(...)
    FROM raw_transactions;
  EOT
}
```

### 7.3 Unset `prevent_destroy`, replace, restore

`prevent_destroy` *"rejects plans that would destroy or recreate the statement"* — including the recreate you now need. **Terraform does not allow variables in `lifecycle` blocks**, so this cannot be toggled by input; the config must be edited.

Three moves, in order:

```bash
set -euo pipefail

STATEMENT_ADDR='module.flink.confluent_flink_statement.statements["fraud-pipeline"]'

# Capture the current statement identity so we can prove it was replaced.
terraform state show "$STATEMENT_ADDR" | grep -E '^\s+id\s+=' | tee /tmp/stmt-id-before.txt

# 1. Edit the config: comment out `prevent_destroy = true` on THIS resource only.
#    Commit it. This is the change that gets reviewed and approved.

# 2. Replace.
terraform plan -replace="$STATEMENT_ADDR" -out=migrate.tfplan
terraform apply migrate.tfplan

# 3. Restore `prevent_destroy = true` and commit. Do not leave it off.
```

For a single-resource layout the address is simply `confluent_flink_statement.fraud_pipeline`. The map form above matches `fsi-dsp`'s `for_each = var.flink_statements` module.

### 7.4 Verify the rebind

Replacement produces a **new statement identity**. If the ID is unchanged, nothing happened.

```bash
set -euo pipefail

terraform state show "$STATEMENT_ADDR" | grep -E '^\s+id\s+=' | tee /tmp/stmt-id-after.txt

if diff -q /tmp/stmt-id-before.txt /tmp/stmt-id-after.txt >/dev/null; then
  echo "FAIL: statement ID unchanged — replacement did not occur"
  exit 1
fi

confluent flink statement describe "$NEW_STATEMENT_NAME" \
  --environment "$ENV_ID" --output json | jq '.status.phase'
# expect "RUNNING"
```

Then confirm output records are actually landing in `scored_transactions` — a `RUNNING` phase alone is not evidence the UDF is being applied.

**Migrate one pipeline at a time.** Each is a destroy-and-recreate of a running job.

---

## 8. Retire v1 — separate, deliberate, ordered

Only after every consumer is confirmed migrated. Order matters and is not interchangeable.

```bash
set -euo pipefail

# 1. Re-run the §7.1 enumeration. Confirm nothing — running, stopped, or
#    failed — still references fraud_score.
# 2. Drop the old function.
```

```sql
DROP FUNCTION fraud_score;
```

```bash
# 3. Only now delete the v1 artifact (remove the resource from Terraform).
```

> **The risk is stopped statements, not running ones.** Confluent: *"Currently running statements are unaffected"* by the drop. A stopped or failed statement whose compiled plan pins the v1 artifact will fail to resume with an artifact-not-found error, and there is no rollback other than recreating the statement.

**Recovery**, if a pinned statement is discovered after the artifact is gone:

```bash
terraform apply -replace='<statement_address>'
```

This forces recompilation against the current function definition. Outside Terraform, drop and recreate the statement manually.

---

## 9. CI/CD

Two workflows. The split is the point: upload is additive, migration destroys running jobs.

```yaml
# .github/workflows/udf-release.yml — build, publish, upload artifact
name: UDF Release
on:
  push:
    tags: ['udf-fraud-score-v*']

jobs:
  build-publish:
    runs-on: ubuntu-latest
    outputs:
      version: ${{ steps.extract.outputs.version }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '17'      # CC Flink supports 11-21; do not float
      - id: extract
        run: echo "version=${GITHUB_REF_NAME#udf-fraud-score-v}" >> "$GITHUB_OUTPUT"
      - run: mvn versions:set -DnewVersion=${{ steps.extract.outputs.version }}
      - run: mvn clean verify deploy
        env:
          JFROG_TOKEN: ${{ secrets.JFROG_TOKEN }}

  upload-artifact:
    needs: build-publish
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          set -euo pipefail
          jf rt download "udf-releases-local/.../udf-fraudscore-${{ needs.build-publish.outputs.version }}.jar" ./build/
          test -s ./build/udf-fraudscore-${{ needs.build-publish.outputs.version }}.jar
      - uses: hashicorp/setup-terraform@v3
      - run: terraform init
        working-directory: terraform/environments/prod
      # Artifact upload only — additive, safe to auto-apply.
      - run: terraform apply -auto-approve -target=confluent_flink_artifact.fraud_score
        working-directory: terraform/environments/prod
        env:
          CONFLUENT_CLOUD_API_KEY:    ${{ secrets.CONFLUENT_CLOUD_API_KEY }}
          CONFLUENT_CLOUD_API_SECRET: ${{ secrets.CONFLUENT_CLOUD_API_SECRET }}
          TF_VAR_udf_version:         ${{ needs.build-publish.outputs.version }}
```

```yaml
# .github/workflows/udf-migrate.yml — statement replacement, manually gated
name: UDF Statement Migration
on:
  workflow_dispatch:
    inputs:
      statement_address:
        description: 'Terraform address of the statement to replace'
        required: true

jobs:
  migrate:
    runs-on: ubuntu-latest
    environment: production      # protection rule → manual approval
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - run: terraform init
        working-directory: terraform/environments/prod
      # NOTE: GitHub Actions does not support YAML anchors/aliases — the env
      # block must be repeated verbatim on each step. Factoring it out with
      # `&anchor`/`*alias` fails at workflow parse time.
      - run: terraform plan -replace='${{ inputs.statement_address }}' -out=migrate.tfplan
        working-directory: terraform/environments/prod
        env:
          CONFLUENT_CLOUD_API_KEY:    ${{ secrets.CONFLUENT_CLOUD_API_KEY }}
          CONFLUENT_CLOUD_API_SECRET: ${{ secrets.CONFLUENT_CLOUD_API_SECRET }}
          # Region-scoped Flink key — required for statement operations.
          TF_VAR_flink_api_key:       ${{ secrets.FLINK_API_KEY }}
          TF_VAR_flink_api_secret:    ${{ secrets.FLINK_API_SECRET }}
      - run: terraform apply migrate.tfplan
        working-directory: terraform/environments/prod
        env:
          CONFLUENT_CLOUD_API_KEY:    ${{ secrets.CONFLUENT_CLOUD_API_KEY }}
          CONFLUENT_CLOUD_API_SECRET: ${{ secrets.CONFLUENT_CLOUD_API_SECRET }}
          TF_VAR_flink_api_key:       ${{ secrets.FLINK_API_KEY }}
          TF_VAR_flink_api_secret:    ${{ secrets.FLINK_API_SECRET }}
```

Dev and staging can auto-apply both. **Prod statement migration is `workflow_dispatch` with an environment protection rule** — it destroys and recreates a running job, and it requires a `prevent_destroy` config change that should be reviewed on its own.

---

## 10. Rollback

| Situation | Action |
|---|---|
| v2 UDF misbehaving after migration | Re-point consuming statements back to `fraud_score` (v1) and `-replace` them. This works **only because v1 was never dropped** — which is the whole reason for the versioned-name strategy. |
| Bad SQL logic | Fix and `-replace` again. Not an in-place update. |
| Statement pinned to a deleted artifact | `terraform apply -replace='<statement_address>'` to force recompilation |
| State drift / partial apply | `terraform plan` before every apply, always |

---

## 11. Pitfalls checklist

- [ ] Artifact `display_name` carries an explicit version — never `latest`
- [ ] `credentials` block present on **every** `confluent_flink_statement`, with a **region-scoped Flink API key**
- [ ] Provider pinned to a minor (`~> 2.85`), not floating on `>= 2.x`
- [ ] JAR built on Java 11–21, toolchain pinned in `pom.xml` and in CI
- [ ] Artifact region matches the compute pool region
- [ ] Function name versioned (`_v2`) — not overwriting in place
- [ ] Migration uses `-replace=`, never a plain `apply`
- [ ] `prevent_destroy` unset → replace → restored, as a reviewed config change
- [ ] Statement ID confirmed **changed** after replacement (§7.4)
- [ ] **Stopped and failed** statements enumerated before any drop (§7.1)
- [ ] v1 function and artifact retired only after the reference check passes
- [ ] Private networking: `private_rest_endpoint` or `flink${endpoint_suffix}`, not the public endpoint
- [ ] OIDC: Identity Pool holds `Assigner` on the service account
- [ ] Artifact/statement state in the same backend as the rest of the environment

---

## 12. Unverified — confirm before relying on

1. ~~**Granular RBAC**~~ — **RESOLVED from local canon.** `wiki/concepts/flink-confluent-cloud-setup.md:59-69` already documents the dual control-plane/data-plane model and the exact roles. See §1 — no scoped-RBAC guesswork needed.
2. **⚠️ Java artifact size limit.** Python UDF artifacts are documented at 100 MB. **No Java limit was found** — do not assume parity.
3. **⚠️ No live-environment validation.** `mcp-confluent` failed to connect when this runbook was written; nothing here was executed against a real Confluent Cloud org. Every command is doc-derived. Run §5 and §7 in dev first.

---

## 13. fsi-dsp integration

`raw/repos/fsi-dsp` has **no UDF or artifact coverage** — `modules/flink` provisions compute pools and statements only, and `confluent_flink_artifact` appears nowhere in the repo. Adopting this runbook means **extending** that module, not just calling it.

What aligns already:

- Provider `~> 2.0` (`modules/flink/main.tf:26-31`) — tighten to `~> 2.85`
- `credentials` block correctly present (`modules/flink/main.tf:89-92`) — the pattern this runbook's earlier draft dropped
- Service-account principals — pitfall 6 in `reference/flink-sql/README.md`
- `prevent_destroy` on statements (`main.tf:98`) — **now known to block UDF migration**; the module needs a documented unset/replace/restore procedure or a per-statement opt-out

Suggested module additions: a `flink-artifact` sub-module, and an `artifact_id` input threaded into `var.flink_statements` so `CREATE FUNCTION` statements can reference it without hand-copying.

---

## Related

- `wiki/patterns/cc-egress-privatelink-managed-connector.md` — private networking endpoint selection
- `wiki/patterns/terraform-cicd-confluent-private-networking.md` — plane split and CI runner placement
- `raw/repos/fsi-dsp/reference/flink-sql/README.md` — CC Flink SQL pitfalls 1–6
- Confluent: `flink/how-to-guides/create-udf.html` — §"Update a UDF safely", §"Recover a statement pinned to a deleted artifact"
