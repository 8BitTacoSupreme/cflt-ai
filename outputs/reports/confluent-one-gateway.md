# Confluent "One Gateway" — What It Actually Is

**Query:** Tell me everything you can about Confluent One Gateway
**Mode:** report | **Route:** `[ROUTE: deep]` | **Date:** 2026-08-05

---

## Answer

**"One Gateway" is not a Confluent product name.** I checked the Confluent Gateway overview, release notes, custom-domains, and deployment docs plus general web search — the string does not appear as a product, SKU, or feature. Two real things it almost certainly refers to, and they are unrelated:

1. **Confluent Gateway** — the Kafka-protocol-aware proxy. Shipped under two doc surfaces with one binary (`confluentinc/cpc-gateway`): **Confluent Private Cloud Gateway (CPC Gateway)** and **Confluent Cloud Gateway**. This is what people mean when they say "the gateway" in a migration/DR conversation. **Most likely referent.**
2. **"One gateway per environment per region"** — the PrivateLink / PNI access-point rule in Confluent Cloud networking: a single ingress gateway fronting Kafka + Schema Registry + Flink + Connect on Enterprise clusters. This is a *networking* resource, not a proxy.

If someone said "One Gateway" in a CPC or migration context, they meant #1. If they said it in a PrivateLink/Terraform context, they meant #2. The rest of this report covers both, weighted toward #1.

---

## Part 1 — Confluent Gateway (the protocol proxy)

### What it is

A cloud-native, **Kafka-protocol-aware** proxy that sits between clients and clusters. Unlike an L4 load balancer (NLB, HAProxy, Azure ILB), it parses the Kafka wire protocol and **rewrites `Metadata` responses in-band** — so clients receive gateway-controlled broker hostnames and use *those* for subsequent produce/fetch connections. DNS aliasing alone cannot do this, which is the whole reason the product exists.

Deployed as a **centralized ingress proxy tier**, not a sidecar.

### Architecture — three primitives

| Primitive | What it is |
|---|---|
| **Routes** | The virtualized endpoints clients connect to. `name`, `endpoint` (`host:port`), `brokerIdentificationStrategy`, and a reference to a streaming domain. |
| **Streaming Domains** | Logical representation of an upstream Kafka cluster — bootstrap servers, TLS material, node-ID ranges. |
| **Policies / Filters** | Governance enforced centrally at the gateway: fencing, schema validation, encryption, data contracts. |

A cutover is: **repoint a route at a different streaming domain.** That is the entire mechanism behind both DR switchover and migration.

### Broker identification — the design decision that matters

Two strategies, chosen per route:

- **`port`** (default) — each upstream broker gets its own port on the gateway. Requires `nodeIdRanges` on the streaming domain. Simple, no DNS work, but burns a port range and doesn't scale elegantly across many clusters.
- **`host`** — SNI-based routing with a hostname pattern, e.g. `broker-$(nodeId).example.com:9092`. Requires **wildcard DNS** (`*.mycluster.kafka`) and clients that present SNI. This is the one you want for custom domains and multi-cluster fronting.

```yaml
routes:
  - name: payments-prod
    endpoint: kafka.fsifirm.com:10000
    brokerIdentificationStrategy:
      type: host
      pattern: "broker$(nodeId).mycluster.kafka"
    streamingDomain:
      name: prod-us-east
      bootstrapServerId: SASL_SSL-1
```

### Capabilities

| Capability | Detail |
|---|---|
| **Custom domains** | Stable client-facing FQDN decoupled from cluster identity. Gateway rewrites advertised listeners. |
| **Network isolation** | Brokers stay entirely private; gateway is the sole reachable endpoint. Three documented patterns: same-VPC (private hosted zone), cross-VPC (peering/TGW + shared zone), external (public hosted zone). |
| **Auth swapping** | Terminate one mechanism client-side, present another broker-side. Documented pairs include SASL/SCRAM→SASL/PLAIN (CC API keys), OIDC→SASL, OAuth→OAuth, and NONE. Credentials pulled from external secret stores: AWS Secrets Manager, HashiCorp Vault, Azure Key Vault, **CyberArk Conjur** (1.3.0). |
| **Fencing** | Per-route filter: `fence.scope: ALL\|NONE`, configurable `errorCode` (default `BROKER_NOT_AVAILABLE`) and `errorMessage`. Used to quiesce traffic before a cutover, or to blast-radius a rogue client. |
| **Centralized governance** | 1.3.0, **Early Access, Docker-only** — validates messages and enforces data contracts at the gateway rather than per-client. |
| **Blue/green upgrades** | Route repoint between old and new cluster versions. |

### Version history

| Version | Contents |
|---|---|
| **1.0.0** | GA. Core protocol routing, auth swapping with credential storage, routes + streaming domains. |
| **1.1.0** | License management — Trial and Enterprise modes. |
| **1.2.0** | SASL/SCRAM, NONE auth, **fencing filter**, librdkafka 2.0.0–2.13.0 support. |
| **1.3.0** (current) | Centralized governance enforcement (EA), OAuth→OAuth swap, CyberArk Conjur, fencing filter ordering fix, SCRAM→NONE bugfix. |

> **Correction to the wiki:** `wiki/concepts/confluent-cloud-gateway.md` flags "1.1.0 GA vs 1.2 fencing" as unverified. Actual: **1.0.0 was GA**; 1.1.0 added licensing; fencing landed in **1.2.0**. Current release is **1.3.0**.

### Protocol support — the hard constraint

**Kafka protocol 3.x and 4.x only. 2.x is unsupported.** For an FSI client estate with long-lived legacy apps, this is the first thing to audit — it can disqualify the gateway for exactly the ancient clients you most wanted to migrate without touching. librdkafka is explicitly qualified at 2.0.0–2.13.0.

### Deployment and operations

- **Docker** and **Confluent for Kubernetes (CFK)**. Still **self-managed** — there is no fully-managed Confluent Cloud SKU for the gateway.
- Licensing: **Trial mode** is the default and caps you at **4 routes**, no key needed. Enterprise mode requires `GATEWAY_LICENSES` (newline-delimited, env var or compose `environment:` block).
- Admin/metrics endpoint on **port 9190** by default: `/metrics` (Prometheus) and `/livez`. JVM metrics are opt-in per class (`JvmGcMetrics`, `JvmMemoryMetrics`, `JvmThreadMetrics`, `ProcessorMetrics`, `UptimeMetrics`) plus `commonTags` for host/region labelling.
- **Stateless** with respect to Kafka data — offsets, transactions, and consumer group state all live in the upstream cluster. HA is multiple replicas behind a TCP LB or a multi-endpoint bootstrap list; failover between replicas is connection-level.

```yaml
gateway:
  image: confluentinc/cpc-gateway:<version_tag>
  name: <gateway_instance_id>
  streamingDomains: []
  secretStores: []
  routes: []
  admin:
    bindAddress: 0.0.0.0
    port: 9190          # /metrics and /livez — scrape target for Prometheus/Grafana
  environment:
    GATEWAY_LICENSES: |
      <license_key>
```

### Use case 1 — client migration (KCP integration)

Confluent extended **KCP** in Q2 2026 to drive gateway-based client migration off MSK/self-managed Kafka. Workflow:

1. Deploy the gateway with streaming domains for **both** source and destination clusters.
2. Plan **migration groups** — logical units of related topics plus the apps that touch them.
3. Onboard clients to the gateway bootstrap endpoints (this is the only client-side change, and it's one-time).
4. Cut over group by group with three KCP commands:
   - **init** — validates infra, Cluster Linking config, consumer offset sync. No traffic change.
   - **lag-check** — live terminal dashboard on replication lag; wait for acceptable.
   - **execute** — pause traffic → promote mirror topics → switch routes atomically → resume.

Producer blocking is seconds; consumers see effectively zero downtime because offsets are synced. Auth is handled by the swap layer — SASL/SCRAM client credentials translate to CC API keys from the secret store, so clients never learn they moved.

**Limitations:** a migration group cuts over all-at-once (no separate producer/consumer phasing); principal- and topic-level granularity is future work; **rollback exists only until topic promotion completes.**

### Use case 2 — DR switchover

Pattern: Cluster Linking replicates active→passive; the gateway owns the client-side switchover that Cluster Linking alone leaves as a manual client reconfiguration. On failover the gateway **closes in-flight connections**, forcing clients to re-bootstrap against the promoted cluster. Planned mode does a graceful close with Cluster Linking reversal; unplanned mode promotes mirror topics immediately.

Confluent's own 60-second-RTO POC is explicitly **not production software** — read the caveats as a requirements list, not a disclaimer:

- **Schema Registry failover is unsupported.**
- **Consumer group state requires manual management.**
- **Cluster Linking does not support transactions on mirror topics** — a real problem for EOS workloads and dangerous on failback.
- POC scope was single-region, Dedicated clusters, public endpoints, **OAuth2 required** (because OAuth2 and Identity Pools are org-scoped in CC, so the same client ID/secret works across clusters — with API keys you'd need per-cluster credentials).

**FSI read:** the gateway moves *connections*, not *state*. For stateless producer/consumer apps, gateway + Cluster Linking is a sound sub-minute RTO story. For Kafka Streams (changelog/repartition topics, RocksDB) or in-flight EOS transactions, it is not — Cluster Linking doesn't replicate the state surface and doesn't carry transactions across mirrors. Pair with an explicit state-rebuild plan or budget the reset into your RTO.

### Use case 3 — secure external/partner access

Brokers stay private; the gateway is the only public surface, terminating mTLS and enforcing policy centrally. Combined with fencing and per-route auth, this is a cleaner partner-access story than punching broker-level ACLs and public endpoints.

### When to use it

- Migrating a large client estate to Confluent Cloud where coordinating app redeploys is the actual blocker.
- Sub-minute DR RTO on **stateless** workloads with Cluster Linking already in place.
- Auth bridging — legacy mTLS/SCRAM client population against a modern OAUTHBEARER cluster, without a coordinated client rollout.
- Multi-tenant traffic control where fencing a client at the proxy beats an ACL roll.
- Regulated environments wanting cluster identity kept out of client configs entirely.

### When not to

- **CC-only greenfield** with native PrivateLink and Cluster Linking already working — you're adding an operational tier for limited gain.
- **Stateful Kafka Streams DR** where the goal is failover without state loss.
- **Latency-critical paths** — parse + re-encode of every Kafka frame is a real p99 tail cost. Measure first.
- **Kafka 2.x clients in the estate** — hard incompatibility.

---

## Part 2 — "One gateway per environment per region" (PrivateLink / PNI)

Distinct concept, same word. In Confluent Cloud networking:

- **Enterprise clusters:** one ingress gateway covers **Kafka + Schema Registry + Flink + Connect** in that environment/region. Terraform `confluent_schema` and `confluent_flink_statement` resolve through the same gateway — though SR DNS should be confirmed independently, not assumed from a working Kafka path.
- **Dedicated clusters:** Flink needs its **own** gateway in the same region; it does not share the Kafka one.
- **Limit:** one gateway per environment per region, up to **10 endpoints**. If you outgrow 10, split environments — not gateways.
- **Egress PrivateLink** (Flink reaching out to e.g. AWS KMS for field-level encryption): Enterprise only, one gateway per region per environment.
- **PNI:** a single PNI gateway can front multiple Enterprise and Freight clusters in the same region/environment; access points need no zonal alignment and route all zones through one private endpoint.

This gateway operates at the **network layer** (VPC endpoints, DNS). Confluent Gateway operates at the **Kafka protocol layer**. They compose — PrivateLink for private reach, Confluent Gateway for protocol-level routing — and are frequently deployed together.

---

## Wiki Sources Consulted

- `wiki/concepts/confluent-cloud-gateway.md` — primary source for the protocol-proxy product; capability table, DR switchover mechanics, FSI considerations. `last_validated: 2026-05-18` (79 days — inside the 90-day window). Three of its four `⚠️ unverified` flags are resolved by this report.
- `wiki/concepts/private-networking.md` — "one gateway, multiple services" for Enterprise; one gateway per environment per region, ≤10 endpoints.
- `wiki/patterns/flink-coe-aws-privatelink-refarch.md` — Enterprise shares a gateway across Kafka+Flink+SR+Connect; Dedicated needs its own for Flink; egress PrivateLink scoping.
- `wiki/patterns/terraform-cicd-confluent-private-networking.md` — Terraform resolution through the shared gateway; confirm SR DNS separately.

**No wiki article covers the term "One Gateway" itself** — because it isn't a product. No auto-stub queued (the underlying topic is covered).

## MCP / Source Validation

| Claim | Source | Result |
|---|---|---|
| "One Gateway" is an official Confluent product/feature name | confluent-docs (overview, release notes, custom-domains, deploy), web | **Corrected — does not exist** |
| Confluent Gateway is protocol-aware, rewrites metadata | confluent-docs | Confirmed |
| Three primitives: routes, streaming domains, policies | confluent-docs | Confirmed |
| Fencing added in 1.2, not 1.1 | confluent-docs release notes | **Corrected** (wiki flagged this as unverified) |
| 1.0.0 was the GA release, not 1.1.0 | confluent-docs release notes | **Corrected** |
| Self-managed only; Docker + CFK; no managed CC SKU | confluent-docs | Confirmed |
| Kafka protocol 3.x/4.x only, 2.x unsupported | confluent-docs | Confirmed |
| librdkafka 2.0.0–2.13.0 supported | confluent-docs release notes | Confirmed |
| Trial mode capped at 4 routes | confluent-docs deploy guide | Confirmed |
| Admin/metrics on port 9190, `/metrics` + `/livez` | confluent-docs deploy guide | Confirmed |
| `brokerIdentificationStrategy` host vs port, wildcard DNS + SNI | confluent-docs custom-domains | Confirmed |
| Secret stores: AWS SM, Vault, Azure KV, CyberArk Conjur | confluent-docs + KCP blog | Confirmed |
| KCP three-command migration flow (init / lag-check / execute) | Confluent blog | Confirmed |
| Cluster Linking does not support transactions on mirror topics | Confluent blog (DR POC) | Confirmed |
| Governance enforcement is EA, Docker-only in 1.3.0 | confluent-docs release notes | Confirmed |
| Exact CFK CRD names/kinds for the gateway | confluent-docs (operator overview is a nav hub only) | **Unverifiable** — needs `co-gateway-deploy.html` |
| Sizing heuristic (1.5–2× broker CPU) | — | **Unverifiable** — remains a generic proxy heuristic, not a Confluent number |

## Canon Compliance

Consistent with Confluent Canon. Reinforcing points:

- **Cluster Linking > MirrorMaker 2** for Confluent-to-Confluent replication holds — the gateway is the client-side complement to CL, not a replacement for it.
- **Security:** the gateway is a good fit for the mTLS + RBAC mandate — terminate FSI client certs at the gateway, hold broker-side credentials in Conjur/Vault, rotate client certs independently. Audit every connection, auth swap, and routing decision to SIEM alongside broker audit logs.
- **Exactly-once:** the CL-no-transactions-on-mirror-topics constraint directly contradicts naive EOS-preserving DR claims. For regulatory reporting workloads, do not represent gateway+CL failover as exactly-once-preserving.
- **Vendor backing:** Confluent Gateway is a Confluent-supported, licensed product — satisfies the FSI vendor-contract rule. Envoy Kafka filters and custom Netty proxies do not.

## Recommended Follow-Ups

1. Audit the client estate for **Kafka protocol < 3.0** before scoping any gateway work.
2. Pull `co-gateway-deploy.html` to pin CFK CRD kinds and the HA/replica model.
3. Load-test the proxy hop against your p99 budget before committing it to a tier-1 path.
4. Update `wiki/concepts/confluent-cloud-gateway.md` — version history correction, protocol-version constraint, the three-primitive model, and the KCP migration path are all missing. Run `/ask --mode reconsolidate` to apply.

---

*Validated against Confluent docs and Confluent engineering blogs (2026-08-05). 17 claims checked, 3 corrected, 2 unverifiable.*

**Sources:**
- [Confluent Private Cloud Gateway Overview](https://docs.confluent.io/private-cloud-gateway/current/overview.html)
- [Confluent Private Cloud Gateway Release Notes](https://docs.confluent.io/private-cloud-gateway/current/gateway-release-notes.html)
- [Custom Domains and Network Isolation](https://docs.confluent.io/private-cloud-gateway/current/gateway-custom-domains.html)
- [Configure and Deploy CPC Gateway using Docker](https://docs.confluent.io/private-cloud-gateway/current/gateway-deploy.html)
- [Deploy and Manage Confluent Cloud Gateway](https://docs.confluent.io/cloud/current/cp-component/gateway/overview.html)
- [Confluent Gateway on CFK — Deployment Overview](https://docs.confluent.io/operator/current/gateway/co-gateway-overview.html)
- [Building Kafka Client Failover: A 60-Second DR POC](https://www.confluent.io/blog/kafka-client-failover-poc-confluent-cloud-gateway/)
- [Kafka Client Migrations With KCP and Confluent Cloud Gateway](https://www.confluent.io/blog/client-migration-kcp-gateway/)
- [Introducing Confluent Private Cloud](https://www.confluent.io/blog/introducing-confluent-private-cloud/)
- [Networking on Confluent Cloud](https://docs.confluent.io/cloud/current/networking/overview.html)
- [Use Private Network Interface connections with Confluent Cloud on AWS](https://docs.confluent.io/cloud/current/networking/aws-pni.html)
- [confluentinc/cpc-gateway — Docker Hub](https://hub.docker.com/r/confluentinc/cpc-gateway)
