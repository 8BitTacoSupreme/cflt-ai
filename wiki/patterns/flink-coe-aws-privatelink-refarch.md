---
title: Flink COE — AWS VPC / PrivateLink Reference Architecture
tags: [flink, confluent-cloud, coe, privatelink, vpc, aws, networking, fsi, stub]
sources:
  - outputs/reports/flink-confluent-cloud-setup-privatelink-architecture.md
  - outputs/reports/flink-privatelink-diagrams.md
  - https://docs.confluent.io/cloud/current/flink/concepts/flink-private-networking.html
related: [patterns/flink-coe-managed-cc-overview, concepts/confluent-cloud-private-networking, patterns/terraform-cicd-confluent-private-networking, patterns/flink-coe-security]
confidence: low
last_updated: 2026-07-30
last_validated: 2026-07-30
---

# Flink COE — AWS VPC / PrivateLink Reference Architecture

> ⚠️ Stub — seeded with validated facts; expand into a full AWS ref arch (diagrams + Terraform) per your organization's account/region topology. Gateway mechanics live in [Private Networking](../concepts/confluent-cloud-private-networking.md); the CI/CD-over-PL runner model lives in [Terraform CI/CD over Private Networking](terraform-cicd-confluent-confluent-cloud-private-networking.md).

## Summary

<!-- Used verbatim in _index.md -->
AWS VPC/PrivateLink reference-architecture sub-page for the [Flink COE](flink-coe-managed-cc-overview.md). Two network paths matter and only one is yours to wire: **Flink→Kafka is always internal to Confluent Cloud** (no config), while **client→Flink** (CLI/Console/Terraform/REST hitting the Flink control plane) is what PrivateLink governs. On **Enterprise** clusters one gateway covers Kafka + Flink + SR + Connect; on **Dedicated** clusters Flink needs its **own** gateway in the same region.

## Pattern

### Two network paths (seed — validate before production commit)

1. **Flink → Kafka: always internal to CC.** Never traverses PrivateLink or the public internet; no configuration. The compute pool reaches the cluster over Confluent's fabric.
2. **Client → Flink: PrivateLink-governed.** SQL Workspaces (Console), `confluent flink shell`, `confluent_flink_statement` (Terraform), and the REST API all hit the Flink control-plane endpoint — that path is what you make private.

### Do you need a separate PrivateLink for Flink?

| Cluster type | Separate Flink gateway? | Shape |
|---|---|---|
| **Enterprise** | **No** — reuse the one ingress PrivateLink Gateway | One Private Endpoint / one PL Service covers Kafka + Flink + SR + Connect |
| **Dedicated** (PL, Peering, or TGW for Kafka) | **Yes** — Flink needs its own gateway in the **same region** | Two Private Endpoints, each targeting a different Confluent PL Service alias, sharing one Private DNS Zone |

- Gateway model: PrivateLink Attachment (PLATT) was superseded by the **ingress PrivateLink Gateway** (AWS 2026-02-12); existing PLATTs still function. See [Private Networking](../concepts/confluent-cloud-private-networking.md).
- **Egress PrivateLink** (niche): Flink statements reaching *out* to an external service (e.g. AWS KMS for field-level encryption) — Enterprise only, one gateway per region per environment.

### AWS wiring (seed)

- **VPC interface endpoint** targeting the Confluent **PL Service alias** (recorded from Network Management → "For serverless products" → PrivateLink).
- **Route 53 private hosted zone** with a wildcard mapping the Flink access-point domain (`*.<region>.aws.private.confluent.cloud`) to the endpoint — two-step CNAME resolution (Confluent Global DNS Resolver strips `glb`, your resolver maps to the endpoint). Wildcard the zone; don't hardcode.
- **Access Point** registers the endpoint back to the gateway.

### DevOps flow (the FSI pattern)

- **Developers get no direct CLI/Console access.** All Flink SQL is version-controlled and deployed via a **self-hosted CI/CD runner inside your VPC** (required for PrivateLink reachability), calling `confluent_flink_statement` (preferred, IaC) or the REST API over the Private Endpoint.
- This is the same in-VPC runner model as [Terraform CI/CD over Private Networking](terraform-cicd-confluent-confluent-cloud-private-networking.md) — the Flink control-plane endpoint (`flink.<region>.aws.private.confluent.cloud`) is another private data-plane target the ARC runner must resolve and reach (SG allows 443, node pool spans the endpoint AZs).

## Caveats

- The `fsi-dsp` setup notes are written for Azure; AWS is analogous (Private Endpoint → VPC interface endpoint, Private DNS Zone → Route 53 PHZ). Validate the AWS domain pattern against current docs before production delivery.
- <!-- TODO: add the three mermaid diagrams (Dedicated dual-gateway, Enterprise single-gateway, DevOps CI/CD flow) and the confluent_flink_statement HCL + curl REST examples from outputs/reports/flink-privatelink-diagrams.md -->

## Related

- [Flink COE — Overview](flink-coe-managed-cc-overview.md)
- [Private Networking](../concepts/confluent-cloud-private-networking.md) — PrivateLink Gateway mechanics, per-tier matrix, Flink-to-Kafka-stays-internal
- [Terraform CI/CD over Private Networking](terraform-cicd-confluent-confluent-cloud-private-networking.md) — the in-VPC runner that deploys Flink statements over PL
- [Flink COE — Security](flink-coe-security.md) — the auth side of the same boundary
