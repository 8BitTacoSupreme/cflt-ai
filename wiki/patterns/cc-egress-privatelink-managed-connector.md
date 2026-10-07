---
title: Egress PrivateLink for Fully-Managed Connectors (Confluent Cloud → External Services)
tags: [confluent-cloud, connect, networking, privatelink, egress, aws, azure, gcp, fsi, sink-connector]
sources:
  - https://docs.confluent.io/cloud/current/connectors/networking/index.html
  - https://docs.confluent.io/cloud/current/connectors/networking/aws-eap-self-managed.html
  - https://docs.confluent.io/cloud/current/connectors/networking/aws-eap-1st-party.html
related: [concepts/private-networking, concepts/network-connectivity-by-tier, patterns/connect-deployment-models, patterns/terraform-cicd-confluent-private-networking, patterns/flink-coe-aws-privatelink-refarch]
confidence: high
last_updated: 2026-08-07
last_validated: 2026-08-07
---

# Egress PrivateLink for Fully-Managed Connectors (Confluent Cloud → External Services)

## Summary

When a fully-managed Confluent Cloud sink (or source) connector must reach a service that isn't on the public internet — a database in your VPC, a first-party cloud service, or a third-party SaaS exposed over PrivateLink — you route the connector's **outbound** traffic through an **Egress PrivateLink Endpoint** rather than the public path. This is the *connector* egress story, distinct from ingress PrivateLink (clients → cluster) and from static egress IPs (public IPs used by managed connectors where no PrivateLink target exists). The direction is always **egress from Confluent's perspective, inbound from the target's** — a naming trap worth stating explicitly on every engagement. The load-bearing operational fact: **a connector that works and a connector that works *privately* look identical from Confluent's side**, so the pattern is not done until you prove traffic traverses the private path at the target.

## Pattern

### The four documented target categories (AWS)

Confluent documents Egress PrivateLink Endpoints for managed connectors against four target types; a third-party SaaS is handled as a fifth, adapted case:

| Target | Flow |
|---|---|
| **First-party services** | Curated cloud services Confluent lists directly. |
| **Self-managed services (you host)** | You stand up an **internal NLB → VPC endpoint service** in your account, then Confluent connects to it. |
| **Amazon RDS** / **Amazon DocumentDB** | Dedicated guided flows. |
| **Third-party SaaS (e.g. Salesforce Private Connect)** | The SaaS publishes *its own* PrivateLink endpoint service; you consume it via the **"Other"** option + its service name. An adaptation of the self-managed flow where the provider — not you — owns the load balancer. **Confirm the SaaS exposes a targetable AWS endpoint service.** |

Azure (Private Link) and GCP (Private Service Connect) have the analogous first-party / self-managed egress flows. Note this differs from **Flink egress PrivateLink**, which is documented for AWS and Azure only — for *connectors*, GCP PSC egress endpoints exist.

### Network prerequisite (this decides the whole UI)

Egress PrivateLink for connectors requires one of:

- **Dedicated cluster** with a Confluent Cloud network whose **Connection type is `PrivateLink Access`** → managed under **Network Management → the network → `Egress connections` tab → Create endpoint**, DNS under the **`DNS` tab**.
- **Enterprise cluster** with a **network gateway** → managed under **Network Management → `For serverless products` tab → the gateway → `Access points` → Add access point**, DNS under the gateway's **`DNS` tab**.
- **PNI (Private Network Interface)** is an alternative (Enterprise/Freight) that routes connector traffic through ENIs in your account *without* PrivateLink infrastructure — different mechanism.

The field values (endpoint name, PrivateLink service name, HA option) are the same across Dedicated and Enterprise; only the navigation differs.

### The self-managed flow (AWS, canonical)

1. Identify the target service's private IP(s) + AZ.
2. **Target group(s)** — IP-type, TCP, one per service port.
3. **Internal Network Load Balancer** — one TCP listener per port → its target group.
4. **VPC endpoint service** over that NLB — **Acceptance required**; note its **service name**.
5. **Allow Confluent's principal (ARN)** on the endpoint service (ARN is shown in the CC **Egress PrivateLink Endpoints** tab).
6. **Create the egress endpoint / access point** in CC with that service name (HA optional).
7. **Accept the endpoint connection request** on the AWS side → endpoint goes **Ready**.
8. **(Optional) DNS record** — map the target hostname to the access point. If skipped, configure the connector with the **VPC endpoint DNS name** as its hostname.
9. **Create the connector**, pointing at the mapped hostname.

For a SaaS-published service (Salesforce et al.), steps 1–5 are the provider's responsibility; you start at step 6 with the provider's service name, and the provider performs the "accept" (step 7) on their side.

### Terraform

The IaC surface is `confluent_access_point` (the egress endpoint) + `confluent_dns_record`. These are **data-plane-adjacent** management resources — see [Terraform CI/CD over Private Networking](terraform-cicd-confluent-private-networking.md) for the plane split and runner placement.

### Validating the private path (do not skip)

Because success looks identical over public and private paths:

1. Check the **target's** access logs and confirm the source is the private connection, not a public IP.
2. **Enforce** at the target — e.g. restrict the integration principal to the private connection — so public-path traffic **fails loudly** instead of silently succeeding.
3. Re-run under enforcement; if it breaks, the DNS record or endpoint isn't routing privately — fix before relaxing.

## When to Use

- A fully-managed connector must reach a private database (RDS/DocumentDB/self-hosted) or a SaaS over PrivateLink, and public egress is prohibited (FSI default).
- You need the connector to use its **standard** target hostname unchanged — the egress DNS record makes the private path transparent.
- Reaching a third-party SaaS (Salesforce, etc.) that publishes an AWS PrivateLink endpoint service.

## Caveats

- **"Ready" ≠ reachable.** The most common failure is a **zonal mismatch** — the target endpoint service's AZs don't overlap Confluent's endpoint AZs; fix with **cross-zone load balancing** on the endpoint service (provider-side for a SaaS target). Also ensure the endpoint service doesn't **enforce inbound rules** that block Confluent's principal.
- **DNS record is optional** — without it you must set the connector's hostname to the VPC endpoint DNS name; with it, the standard hostname routes privately.
- **Not the same as static egress IPs** — those are *public* IPs used by managed connectors when no PrivateLink target exists; egress PrivateLink is the private alternative.
- **Confirm SaaS targetability** — a SaaS must actually publish a consumable AWS endpoint service; not all do.
- **Direction naming** — egress (Confluent) = inbound (target). State it up front to avoid console confusion.
- **Flink vs connector egress differ** — Flink egress PrivateLink is AWS/Azure only; connector egress adds GCP PSC. Don't assume parity.

## Related

- [Private Networking](../concepts/private-networking.md) — the PrivateLink Gateway / access-point mechanics and per-tier matrix this builds on
- [Network Connectivity by Cluster Tier](../concepts/network-connectivity-by-tier.md) — which egress options each cluster tier supports
- [Connect Deployment Models](connect-deployment-models.md) — where fully-managed connectors sit vs self-managed Connect
- [Terraform CI/CD over Private Networking](terraform-cicd-confluent-private-networking.md) — `confluent_access_point` / `confluent_dns_record` as IaC, and runner placement
- [Flink COE — AWS PrivateLink Reference Architecture](flink-coe-aws-privatelink-refarch.md) — the Flink-side egress story (AWS/Azure only)
