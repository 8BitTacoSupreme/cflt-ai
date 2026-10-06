---
title: Terraform CI/CD for Confluent Cloud over Private Networking (GitHub Runners)
tags: [terraform cicd github-actions confluent-cloud networking privatelink vpc fsi iac oidc]
sources:
  - https://docs.confluent.io/cloud/current/clusters/terraform-provider.html
  - https://docs.confluent.io/cloud/current/clusters/terraform-security.html
  - https://registry.terraform.io/providers/confluentinc/confluent/latest
related: [concepts/confluent-cloud-private-networking, patterns/fsi-governance-automation, patterns/schema-registry-adoption-playbook, patterns/topic-naming, patterns/connect-deployment-models]
confidence: high
last_updated: 2026-07-29
last_validated: 2026-07-29
---

# Terraform CI/CD for Confluent Cloud over Private Networking (GitHub Runners)

## Summary

The Confluent Terraform provider operates on **two planes with different network reachability**, and that single fact dictates how you structure GitHub Actions CI/CD when the Confluent Cloud cluster uses private networking (PrivateLink / VPC peering / Private Network Interface / Transit Gateway). Management-plane resources (environments, clusters, networks, service accounts, RBAC, API keys, identity pools) talk to the **public** `api.confluent.cloud`; data-plane resources (topics, ACLs, schemas, Flink statements, connectors) talk to the cluster's **private** REST / Schema Registry endpoint, which has no public IP. A GitHub-*hosted* runner plans the management plane fine and then times out on the first topic — so data-plane Terraform must run on a **self-hosted runner inside the VPC**, the code must be **split by plane into separate state**, and auth should be **GitHub OIDC → Confluent identity pool** (short-lived) rather than long-lived keys. This is the standard shape for a third-party CDC agent (e.g. Precisely, Qlik, Debezium) → Confluent Cloud landing zone, where the runner rides the same private path the CDC agents use.

## Pattern

### The load-bearing constraint: two planes, two reachabilities

| Plane | Representative resources | Endpoint | Reachable from a GitHub-*hosted* runner? |
|---|---|---|---|
| **Management** | `confluent_environment`, `confluent_kafka_cluster`, `confluent_network`, PrivateLink plane-A resources (see below), `confluent_peering`, `confluent_transit_gateway_attachment`, `confluent_service_account`, `confluent_role_binding`, `confluent_api_key`, `confluent_identity_pool`, `confluent_ip_filter` | `api.confluent.cloud` (**public**) | Yes |
| **Data** | `confluent_kafka_topic`, `confluent_kafka_acl`, `confluent_schema`, `confluent_subject_config`, `confluent_flink_statement`, `confluent_connector` | cluster **`rest_endpoint`** / SR endpoint | **No — private, in-VPC only** |

> The reachability split is **provider mechanics**, not a single doc line: the `confluent_kafka_topic` / `confluent_kafka_acl` / `confluent_schema` resources require the cluster or Schema Registry `rest_endpoint` plus a cluster/SR-scoped API key. With private networking those endpoints resolve only inside the VPC, so a public runner fails on them with a connection timeout that looks like — but is not — an auth error. The management-plane resource names, the two-tier auth model, and the security/identity guidance below are all validated against `confluent-docs`.

### 1. Split Terraform by plane (separate state)

Do not apply both planes in one run from a public runner — the management plane succeeds and the data plane fails, leaving a half-applied environment. Use two root modules:

- **`platform/` (management plane)** — environment, network, private-link attachment, cluster, service accounts, RBAC, identity pools, API keys. Changes rarely; gate behind manual approval. Outputs cluster `id` and `rest_endpoint`.
- **`data/` (data plane)** — topics, schemas, subject configs, ACLs, Flink statements. Consumes `platform` outputs via `terraform_remote_state`. This is the high-churn layer app teams PR into.

If a single config is unavoidable, use **two provider aliases** (default block on cloud keys for management; a `kafka`-aliased block bound to the cluster `rest_endpoint` + cluster API key for data) — but separate state is cleaner and safer.

### 2. Runner topology — self-hosted, in the VPC

Run **self-hosted ephemeral runners inside the VPC** (or a CI subnet peered to it) that carries the private path to Confluent Cloud — via **Actions Runner Controller (ARC) on EKS** or an ASG-backed pool. The data-plane job *must* land here. Three things that bite, most common first:

1. **Private DNS resolution.** The runner reaches the PrivateLink ENI but can't resolve `*.<region>.<cloud>.confluent.cloud` or the SR hostname → `no such host`. The runner subnet's resolver must see the Confluent **private hosted zone** (Route 53 PHZ / Azure Private DNS / a `confluent_dns_forwarder`). Looks like an auth bug; isn't.
2. **Egress split.** The runner needs outbound to **both** public `api.confluent.cloud` (management) **and** the private cluster path (data). Over-tight egress breaks the management plane.
3. **IP filters.** If `confluent_ip_filter` is enabled on the management plane, the runner's NAT egress EIP must be in an allowlisted `confluent_ip_group`, or plane-A applies start returning 403.

Do **not** expose the cluster publicly to make GitHub-hosted runners work — it defeats the private networking.

#### PrivateLink specifics

PrivateLink doesn't change the plane split, but it sharpens the runner requirements and dictates the plane-A resources. See [Private Networking](../concepts/confluent-cloud-private-networking.md) for the gateway mechanics.

- **Plane-A resources are tier-dependent.** For **Enterprise** (FSI baseline), use the **ingress PrivateLink Gateway** model: `confluent_gateway` + `confluent_access_point` + your `aws_vpc_endpoint` (/ `azurerm_private_endpoint` / `google_compute_forwarding_rule`). The legacy `confluent_private_link_attachment` (PLATT) is superseded — no new ones after the cutover (AWS 2026-02-12; Azure/GCP 2026-05-04). For **Dedicated**, use `confluent_network` (type `PRIVATELINK`) + `confluent_private_link_access`.
- **DNS is a two-step CNAME + wildcard.** Confluent's Global DNS Resolver strips the `glb` subdomain; your private resolver (Route 53 PHZ / Azure Private DNS / Cloud DNS) wildcard-maps the access-point zone to your VPC endpoint. Broker names are **not static** — wildcard the zone, never hardcode. The runner's resolver must see this PHZ, for **both** Kafka and Schema Registry hostnames.
- **Per-AZ endpoints, ≤10 per gateway.** PL endpoints are per-AZ; the ARC node pool must span the AZs that have an endpoint or a runner pod can land with no path.
- **One gateway covers Kafka + SR + Flink** (Enterprise). So `confluent_schema` (SR) and `confluent_flink_statement` (client→Flink) resolve through the same gateway — but confirm SR DNS specifically, not just Kafka.
- **Management plane stays public under PL.** `api.confluent.cloud` is not behind PrivateLink, so plane A still needs the runner's public egress — the split is required by PL's own boundary, not just convenient.
- **On-prem/mainframe can't reach PL directly.** If third-party CDC agents (e.g. Precisely, Qlik, or z/OS Connect CDC) are on-prem, route through a shared-services VPC you own, then PL from there; co-locate the runner in that VPC.

### 3. Auth — OIDC and short-lived, not long-lived GitHub secrets

Confluent's security guidance recommends **identity pools + short-lived secrets** over static keys. For GitHub Actions: **GitHub OIDC → `confluent_identity_provider` + `confluent_identity_pool`**, so the workflow exchanges its OIDC token for a short-lived Confluent credential — no long-lived `CONFLUENT_CLOUD_API_KEY` in GitHub secrets.

- **Least privilege per plane:** a management-plane identity with `EnvironmentAdmin` scoped by `crn_pattern`; a separate data-plane identity scoped to the one cluster. Never a single god-key.
- The **cluster API key** for plane B is itself a `confluent_api_key` output from plane A — pull it at apply time from a cloud secrets manager (Vault / AWS Secrets Manager / GSM / Key Vault), not from a GitHub secret.

### 4. State backend

- Remote backend in-cloud (**S3+DynamoDB lock / GCS / azurerm**), **SSE-KMS encrypted, versioned, IAM-restricted**. State holds API-key secrets and connector configs — treat it as sensitive.
- Reach the backend over a **VPC endpoint** (S3/DynamoDB gateway endpoint) so state ops from the in-VPC runner need no internet egress.

### 5. Pin the provider

```terraform
terraform {
  required_providers {
    confluent = { source = "confluentinc/confluent", version = "2.80.0" }  # current; pin exactly in CI
  }
}
```

## When to Use

- Any Confluent Cloud environment on **private networking** (Enterprise/Dedicated with PrivateLink, peering, PNI, or Transit Gateway) managed as code through GitHub Actions.
- FSI landing zones where public data-plane access is prohibited and CI must run inside the trust boundary.
- **Third-party CDC agent (e.g. Precisely, Qlik, Debezium) → Confluent Cloud pipelines**, where CDC agents already run in-VPC over PrivateLink and Terraform manages the Confluent landing zone (topics, schemas, service accounts, ACLs) — the runner co-locates with the agents' subnet. See the companion runbook's third-party CDC landing zone section.

## Caveats

- **`dial tcp … i/o timeout` on topic/ACL/schema apply** = running on a public (GitHub-hosted) runner. Move plane B to the in-VPC self-hosted runner.
- **`no such host` for the `rest_endpoint`/SR** = private DNS not resolvable from the runner subnet. Attach the Confluent private hosted zone / DNS forwarder to the runner VPC. Schema Registry needs its own private DNS resolution, not just Kafka.
- **"Can't authenticate" on a topic despite a valid cloud key** = used `cloud_api_key` where a **cluster-scoped** key + `rest_endpoint` is required. Use the data-plane provider alias.
- **Single apply, both planes, public runner** = half-applied (cluster created, topics failed). Split state.
- **Plane-A 403 from CI** = `confluent_ip_filter` excludes the runner's egress IP. Allowlist the NAT EIP in a `confluent_ip_group`.
- **`prevent_destroy`** on environment, cluster, and network resources — the provider examples use it; keep it, so a plane-A misapply can't drop the cluster.
- This pattern is provider-mechanics-driven; revalidate the plane split if Confluent ships public-with-private-DNS hybrids or a management proxy that changes data-plane reachability.

## Related

- [Private Networking](../concepts/confluent-cloud-private-networking.md) — PrivateLink Gateway mechanics, PLATT→gateway transition, per-tier connectivity matrix, and the two-step DNS model the runner depends on
- [FSI Governance Automation](fsi-governance-automation.md) — CI/CD governance and policy-as-code context this pipeline slots into
- [Schema Registry Adoption Playbook](schema-registry-adoption-playbook.md) — the `confluent_schema` data-plane resources this pipeline registers (private SR endpoint)
- [Topic Naming](topic-naming.md) — naming conventions for the topics managed in the data plane
- [Connect Deployment Models](connect-deployment-models.md) — where `confluent_connector` resources fit relative to self-managed Connect
