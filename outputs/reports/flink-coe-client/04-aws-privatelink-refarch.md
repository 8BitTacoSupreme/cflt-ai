> Part of **Flink Center of Excellence — Managed Flink on Confluent Cloud** (self-contained series). Validated against Confluent documentation 2026-07-30.

# Part 4 — AWS VPC / PrivateLink Reference Architecture

Two network paths matter, and only one is yours to wire.

1. **Flink → Kafka: always internal to Confluent Cloud.** This path never traverses PrivateLink or the public internet and requires no configuration. The compute pool reaches the cluster over Confluent's internal fabric.
2. **Client → Flink: PrivateLink-governed.** SQL Workspaces (Console), the Flink shell/CLI, `confluent_flink_statement` (Terraform), and the REST API all reach the Flink control-plane endpoint — that path is what you make private.

## Do you need a separate PrivateLink for Flink?

| Cluster type | Separate Flink gateway? | Shape |
|---|---|---|
| **Enterprise** | **No** — reuse the one ingress PrivateLink Gateway | One Private Endpoint / one PrivateLink Service covers Kafka + Flink + Schema Registry + Connect |
| **Dedicated** (PrivateLink, Peering, or Transit Gateway for Kafka) | **Yes** — Flink needs its own gateway in the **same region** | Two Private Endpoints, each targeting a different Confluent PrivateLink Service alias, sharing one Private DNS zone |

- **Gateway model:** the older PrivateLink Attachment (PLATT) was superseded by the **ingress PrivateLink Gateway** (AWS cutover 2026-02-12); existing PLATTs continue to function but new ones should use the gateway model.
- **Egress PrivateLink** (niche): for Flink statements reaching *out* to an external service — for example AWS KMS for field-level encryption — available on Enterprise clusters, one gateway per region per environment.

## AWS wiring

- **VPC interface endpoint** targeting the Confluent **PrivateLink Service alias** (recorded from Network Management → "For serverless products" → PrivateLink).
- **Route 53 private hosted zone** with a wildcard record mapping the Flink access-point domain (`*.<region>.aws.private.confluent.cloud`) to the endpoint. Resolution is a two-step CNAME: Confluent's global resolver returns the access-point name and your private resolver maps it to the endpoint. **Wildcard the zone; never hardcode broker/endpoint names** (they are not static).
- **Access Point** registers the endpoint back to the gateway.

## Deployment flow (the FSI pattern)

- **Developers get no direct CLI/Console access to production.** All Flink SQL is version-controlled and deployed by a **self-hosted CI/CD runner inside your VPC** (required for PrivateLink reachability), which calls `confluent_flink_statement` (preferred, infrastructure-as-code) or the REST API over the Private Endpoint.
- Because the Flink control-plane endpoint (`flink.<region>.aws.private.confluent.cloud`) is a private target, the runner must be able to **resolve it** (private hosted zone attached to the runner's network) and **reach it** (the endpoint's security group allows TCP/443 from the runner's CIDR, and the runner's node pool spans the availability zones that have an endpoint — PrivateLink endpoints are per-AZ). These are the same requirements as any private data-plane Terraform apply.

## Two common failure modes on this path

- **`dial tcp <private-IP>:443: i/o timeout`** — DNS resolved to a private address but the connection timed out. This is reachability, not DNS: the endpoint security group does not allow 443 from the runner, or the runner landed in an availability zone with no endpoint. Confirm with `nc -vz <private-IP> 443`.
- **`no such host`** for the Flink or Schema Registry hostname — the private hosted zone is not resolvable from the runner. Attach/forward the Confluent private hosted zone to the runner's network.

---
