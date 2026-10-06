---
title: Confluent Cloud Cluster SKU Selection
tags: [kafka, confluent-cloud, cluster-types, sku, cli, ephemeral, basic, standard, enterprise, dedicated, freight, gcp, aws, azure, fsi]
sources: [wiki/concepts/cc-cluster-tiers.md, wiki/concepts/network-connectivity-by-tier.md]
related: [concepts/cc-cluster-tiers, concepts/network-connectivity-by-tier, concepts/confluent-cloud-private-networking, concepts/fsi-data-streaming-platform, concepts/sla-tiers, patterns/dr-cluster-linking]
confidence: medium
last_updated: 2026-08-18
last_validated: 2026-08-18
---

# Confluent Cloud Cluster SKU Selection

## Summary

Picking a Confluent Cloud (CC) cluster SKU is a workflow problem distinct from understanding what each SKU *is*. `concepts/cc-cluster-tiers.md` owns the tier mental model; this article owns the **decision path** from a request like *"create a Basic Kafka cluster named `smoke-test-01` in `env-xxxxxx` on GCP `us-east1`"* to a validated `confluent kafka cluster create` invocation, plus the routing logic for production work. It captures the ephemeral / smoke-test pattern (Basic on any cloud, deleted within the day) versus the FSI prod path (Enterprise default, Dedicated when CL destination / VPC peering / schema validation is needed). Note: ksqlDB is NOT a Dedicated-only feature — it's on Basic, Standard, and Dedicated; Enterprise is the one tier that lacks it. Cloud and region availability vary slightly per type and shift frequently — confirm against `confluent-docs` MCP before quoting a customer.

## Detail

### Selection decision tree

Walk top-to-bottom; pick the first matching row. Numbers in parentheses cite per-tier ceilings on `concepts/cc-cluster-tiers.md`.

| Step | Question | If YES → SKU | If NO → next |
|---|---|---|---|
| 1 | Ephemeral, dev/test, demo, or smoke-test? Public networking is fine? Workload will be deleted within days? | **Basic** | Step 2 |
| 2 | Latency-tolerant firehose (logs, telemetry, clickstream); seconds-of-latency acceptable; *no* transactions, *no* EOS, *no* idempotent producers required? | **Freight** | Step 3 |
| 3 | Production workload — needs **VPC peering**, **AWS Transit Gateway**, **schema validation**, **CL destination at scale**, or **single-tenant isolation**? | **Dedicated** | Step 4 |
| 4 | Production workload — needs **private networking** (PrivateLink / PSC / PNI), elastic capacity (no capacity math), mTLS, BYOK, audit log? | **Enterprise** | Step 5 |
| 5 | Smaller production workload — public networking acceptable, fits under 10 eCKU? | **Standard** | Re-examine — workload doesn't map to a public CC SKU; likely a CFK/CP conversation |

For FSI specifically: Basic is **never prod** (no RBAC, no audit log, no mTLS, can't be a CL destination — see `concepts/cc-cluster-tiers.md` "Tier matrix"). The default FSI prod SKU is **Enterprise**; **Dedicated** appears when one of the Step 3 features is non-negotiable.

### Cloud and region availability

Basic, Standard, Enterprise, and Dedicated are all available on AWS, Azure, and GCP today. Freight currently exists on AWS PNI; check `confluent-docs` for the latest Azure/GCP status before quoting.

> ⚠️ unverified — exact region surface per (SKU × cloud) combination; the matrix changes faster than this article. Resolve via `confluent kafka region list --cloud <gcp|aws|azure>` or `confluent-docs` MCP at quote time.

For the originating `/ask` query (Basic on GCP `us-east1`): Basic clusters on GCP are widely available and `us-east1` is a long-standing GCP CC region. If `confluent kafka region list --cloud gcp` shows the region, Basic is creatable there.

### Creation workflow

**Environment scoping.** A CC cluster lives inside an environment (`env-xxxxxx`). The environment determines:

- The Schema Registry instance (one Stream Governance package per environment).
- The Cluster Linking blast radius (CL operates across environments and orgs, but service-account/IAM lives per environment).
- Billing aggregation.

Set the environment explicitly in every `confluent` CLI invocation. Either `confluent environment use env-xxxxxx` once per shell, or pass `--environment env-xxxxxx` on every command. The latter is the correct shape for CI/IaC paths — never depend on shell context.

**CLI shape.** Canonical Basic-cluster create:

```bash
# Smoke-test pattern: Basic, single-zone, GCP us-east1, deleted same-day
confluent environment use env-xxxxxx
confluent kafka cluster create smoke-test-01 \
  --cloud gcp \
  --region us-east1 \
  --type basic \
  --availability single-zone
```

> ⚠️ unverified — `--availability single-zone` is the canonical flag for Basic (Basic is single-AZ); `confluent kafka cluster create --help` or `confluent-docs` MCP for the current CLI surface is the source of truth. Standard/Enterprise/Dedicated require `--availability multi-zone` for prod.

**For prod (Enterprise default).** Same shape, different flags — and a different mental model. Enterprise is private-only; the cluster needs a network resource (PrivateLink / PSC / PNI) attached. The single-line `cluster create` does not provision that network resource; the PrivateLink Gateway / PNI is a separate `confluent network` workflow tracked in `concepts/confluent-cloud-private-networking.md`.

```bash
# Prod skeleton — Enterprise, multi-zone, GCP, attached to a PSC network
confluent kafka cluster create payments-prod \
  --environment env-prod-xxx \
  --cloud gcp \
  --region us-east1 \
  --type enterprise \
  --availability multi-zone \
  --network n-xxxx   # PSC network resource provisioned beforehand
```

### Ephemeral / smoke-test pattern

The original `/ask` query was tagged `Mode: ephemeral`. The pattern that goes with that tag:

1. Create Basic, single-zone, in any region near the engineer.
2. Use a short-lived service account scoped to the smoke-test topic prefix.
3. Run the validation (produce, consume, schema register, whatever the test covers).
4. **Delete the cluster the same day** — Basic billing is hourly; an idle smoke-test cluster left running is the most common source of CC waste.
5. Never wire the cluster into a CI pipeline that survives the engineer leaving. If a CI path needs a Kafka cluster, use a permanent dev cluster in a dedicated dev environment with TTL'd topics — not an ephemeral Basic.

Basic is the right SKU for steps 1–4 precisely *because* it has no RBAC, no audit log, no mTLS, no CL destination capability — those are features you don't need for an ephemeral test and don't want to pay for.

### SKU vs availability vs networking

Three orthogonal axes are easy to conflate. Keep them separate:

- **SKU / type** — Basic, Standard, Enterprise, Dedicated, Freight. Governs feature ceiling, SLA, and capacity model. (`concepts/cc-cluster-tiers.md`)
- **Availability** — `single-zone` or `multi-zone`. Determines RPO/RTO posture and cost. Basic is single-zone; Standard/Enterprise/Dedicated should be multi-zone in prod. (`concepts/sla-tiers.md` for tier-driven targets.)
- **Networking** — public / PrivateLink / PSC / PNI / VPC peering / Transit Gateway. Constrained by SKU (Basic and Standard are public-only; Freight is private; Enterprise is private-only; Dedicated supports all modes). (`concepts/network-connectivity-by-tier.md`)

A common mistake is asking "which SKU?" and answering "Dedicated, because we need PrivateLink" — most of the time Enterprise is the right answer and Dedicated is over-buying. Reverse the order: pick the SKU from the feature-ceiling decision tree (Step 1–5 above), then check that the SKU's networking modes intersect with what your perimeter requires.

### FSI guardrails

- **Basic and Standard are not prod-capable in FSI.** No audit log on Basic; no private networking on either. Either alone is a finding in any FSI cluster-design review.
- **Enterprise is the default prod SKU.** Reach for Dedicated only when a Step-3 feature forces it.
- **Freight is not for transactional workloads.** No idempotent producer, no transactions, no EOS — disqualifies any audit-grade or sub-100ms tier (`concepts/sla-tiers.md`).
- **The fixed invariants apply on every SKU.** `replication.factor=3`, `min.insync.replicas=2`, `unclean.leader.election.enable=false`. Don't write a runbook that assumes you can change these (`concepts/cc-cluster-tiers.md`, gotcha #7 in `synthesis/confluent-gotchas-top-20.md`).

## Related

- [Confluent Cloud Cluster Tiers](cc-cluster-tiers.md) — tier matrix and per-SKU feature ceiling (MCP-validated 2026-05-14)
- [Network Connectivity by Cluster Tier](network-connectivity-by-tier.md) — networking modes mapped to each tier
- [Private Networking](confluent-cloud-private-networking.md) — PrivateLink Gateway / PSC / PNI provisioning workflow
- [FSI Data Streaming Platform](fsi-data-streaming-platform.md) — six deployment models including CC tier selection
- [SLA Tiers](sla-tiers.md) — FSI SLA tier definitions driving multi-zone / RPO / RTO
- [DR — Cluster Linking](../patterns/dr-cluster-linking.md) — which SKUs can source vs destination a CL
