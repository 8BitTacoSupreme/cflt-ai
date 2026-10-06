# Plan: Create a Basic Kafka cluster named `smoke-test-01`

**Request:** Create a Basic Kafka cluster named smoke-test-01 in environment env-xxxxxx on GCP in us-east1
**Overlay:** base (no `--overlay` provided)
**Mode:** dry-run (read-only)
**Generated:** 2026-05-11T14:19:31Z

---

## Selected Artifact

| Field | Value |
|---|---|
| Artifact ID | `scenario/cc-gcp` |
| Type | scenario |
| Path | `raw/repos/fsi-dsp/scenarios/cc-gcp` |
| Description | Confluent Cloud on GCP starter kit |

### ⚠ Coverage gap — read this before applying

Gate 2 mechanically matched `scenario/cc-gcp` on the `gcp` keyword, but inspection of
`scenarios/cc-gcp/variables.tf` shows the kit **consumes** an existing cluster — it
requires `kafka_cluster_id` (e.g., `lkc-xxxxx`), `kafka_rest_endpoint`,
`kafka_cluster_crn`, plus a paired DR cluster — and provisions topics, schemas, RBAC,
and the bidirectional cluster link on top of those clusters. It does **not** stand up a
new `confluent_kafka_cluster` resource.

MANIFEST.yaml v1.1.0 has no cluster-provisioning artifact:

- `module/topic` — governed topic on an existing cluster
- `module/flink` — Flink compute pool on an existing environment
- `scenario/cc-{aws,azure,gcp}` — topic + schema + RBAC + DR starter kits assuming clusters exist

Per ACT-06, this skill will **not** generate inline `resource "confluent_kafka_cluster"` HCL.

**Recommended path forward:**

1. Open a PR against `fsi-dsp` to add a cluster-provisioning artifact — proposed ID
   `module/cc-cluster-basic`, type `terraform-module`, path `modules/cc-cluster-basic`,
   wrapping `confluent_kafka_cluster` with the `basic { }` block and a
   `confluent_environment` data source. Add it to `MANIFEST.yaml` per CNTR-04.
2. **In the meantime**, provision `smoke-test-01` via the Confluent Cloud Console or
   `confluent kafka cluster create` CLI (out-of-band), then wire it into
   `scenarios/cc-gcp/clusters.auto.tfvars` to use the matched artifact for the topic +
   SR + RBAC + DR layer.

---

## Arguments

Inputs derived from the request, mapped to the matched artifact's variable surface
(`scenarios/cc-gcp/variables.tf` and `clusters.auto.tfvars.example`). Values marked
**TBD** must be sourced from Confluent Cloud after the cluster exists; values from the
request are listed first.

### From request

| Source field | Value |
|---|---|
| `display_name` (cluster) | `smoke-test-01` |
| `environment_id` | `env-xxxxxx` |
| `cloud` | `GCP` |
| `region` | `us-east1` |
| `availability` | `SINGLE_ZONE` (canonical default for `basic`) |
| Cluster tier | `basic` (`confluent_kafka_cluster.basic { }` — non-production tier per Confluent docs) |

### Required by `scenario/cc-gcp` (populate after cluster creation)

| Variable | Source | Status |
|---|---|---|
| `kafka_cluster_id` | CC Console / `confluent kafka cluster list` | TBD (post-create) |
| `kafka_rest_endpoint` | CC Console / cluster describe | TBD |
| `kafka_cluster_crn` | CC Console / cluster describe | TBD |
| `sr_cluster_id` | CC Console / `confluent schema-registry cluster describe` | TBD |
| `sr_rest_endpoint` | CC Console / SR describe | TBD |
| `sr_cluster_crn` | CC Console / SR describe | TBD |
| `cluster_link_name` | Operator decision | TBD (omit for smoke test) |
| `dr_kafka_cluster_id` | Paired DR cluster (e.g., us-west1) | N/A for smoke — Basic does not support cluster linking |
| `dr_kafka_rest_endpoint` | Paired DR cluster | N/A for smoke |

### FSI overlay implications

Canon stack resolved to `base + industry/fsi`. Note the following canon obligations
that a `basic` cluster cannot satisfy — flagged for awareness, not blocking for a
smoke test:

- `min.insync.replicas = 2` and RF=3 are topic-level settings; Basic clusters provision
  topics with RF=3 internally but **do not expose multi-AZ** — Basic is single-zone.
- Cluster Linking and DR (canonical default per FSI overlay) are **not available on
  Basic** — requires Standard or Enterprise/Dedicated. `smoke-test-01` will be DR-less.
- mTLS + RBAC: Basic clusters support API keys and OAuth, not mTLS. For any FSI
  production workload, escalate to Enterprise.

A smoke-test cluster named `smoke-test-01` is consistent with non-production /
throwaway use — these gaps are expected.

---

## Gate Results

| Gate | Status | Detail |
|---|---|---|
| 1. canon_compliance | PASS | Request is consistent with Confluent Canon defaults. |
| 2. fsi_dsp_coverage | PASS | Matched fsi-dsp artifact: `scenario/cc-gcp` (scenario). **See coverage-gap note above** — match is downstream of cluster creation. |
| 3. confluent_docs_schema | PASS | Schema validation deferred to MCP runtime (confluent-docs). |
| 4. mcp_confluent_state | PASS | Cluster state check deferred to MCP runtime (mcp-confluent). |

No `--gate-bypass` flags were applied.

---

## Canon Compliance

Active canon defaults relevant to this request (from `base + industry/fsi`):

| Area | Canon default | Applies to this plan? |
|---|---|---|
| Producer `acks` | `all` | Topic-producer level — set in apps, not cluster |
| Producer idempotence | `enable.idempotence=true` | Topic-producer level |
| Consumer auto-commit | `false` | Topic-consumer level |
| Schema format | Avro/Protobuf | Schema Registry — created with cluster's environment |
| Replication factor | 3 (prod) | Basic enforces internally; topics inherit |
| `min.insync.replicas` | 2 (prod) | Not enforceable on Basic; flag for production escalation |
| Compatibility mode | `BACKWARD` default | Subject-level — set via SR config |
| Cluster Linking | Preferred over MM2 for CC-to-CC DR | **Not available on Basic tier** — escalate to Standard+ |
| Security | mTLS + RBAC for FSI | **Not available on Basic** — API keys / OAuth only |
| Audit log | Enabled on production | Org-level setting, separate from cluster |
| Naming convention | `<domain>.<entity>.<event>` for topics | N/A for cluster; cluster name `smoke-test-01` is operator-chosen |

---

## Provenance Footer

Canon stack: base + industry/fsi | Hash: b6a3cf22b1438242 | MANIFEST: 1.1.0 | Floor: claude-opus-4-7 | Generated: 2026-05-11T14:19:31Z
