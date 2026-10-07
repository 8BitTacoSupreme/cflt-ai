# Streaming on Z
### Confluent (Kafka + Flink) on IBM LinuxONE (Emperor 5 / z17 generation) — A GoodLabs Studio Practice Offering

**The systems of record already emit the truth. We make it flow.**

*Post-acquisition, this is IBM's own supported stack — **IBM Confluent Platform for Z and LinuxONE** — not a third-party port. Same vendor as the mainframe.*

---

## The Problem

Every FSI modernization program eventually hits the same wall: the data that matters lives in CICS, IMS, VSAM, and DB2, and every attempt to stream it off-platform stalls on the same three questions — *which on-ramp, what does it cost, and will it survive an audit?* Most engagements burn their first quarter discovering that Data Gate is DB2-only, that CDC licensing doesn't cover the VSAM estate, or that the "quick MQ integration" actually requires application code changes nobody scoped.

We've already made those mistakes on someone else's dime.

## The Offering

**1 — Streaming Readiness Assessment** *(2–3 weeks, fixed fee)*
Every mainframe source scored against our conduit decision framework: app-driven (MQ, SDK) vs. data-driven (zDIH, CDC, Data Gate). Deliverables: conduit map, IFL/broker sizing from our field-tested sizing model, latency and sovereignty requirements, licensing exposure (including the IBM Confluent Platform for Z and LinuxONE software entitlement), and a sequenced backlog. Code-change requirements (the dashed lines) identified and priced honestly — before they become change orders.

**2 — First Stream** *(30–45 days)*
One source **from the pre-mapped conduit set**, one conduit, one sink, production-adjacent. Deployed from our existing Terraform and Ansible asset library for Confluent Platform on LinuxONE — cluster provisioning, Schema Registry governance baseline, OpenTelemetry-native observability, and connector configurations for the common source/sink pairs. Confluent runs on IFLs (Linux on Z), consuming from the z/OS systems of record — not on z/OS itself. You get a running stream and the automation that built it.

**3 — Streaming Platform Buildout** *(quarterly increments)*
Full fan-out to the downstream estate, DR framework, governance operating model, and the premium pattern: **in-transaction AI event streams** — transactions scored at the source of truth by Telum II (on-chip) or Spyre (on-frame accelerator card), with the *scored event* flowing through Confluent and Flink enriching downstream rather than re-inferring. Fraud, AML, and anomaly detection as streaming products, not batch reports.

## Why This Is Fast

This is not a services engagement that starts from a blank page. And because IBM now owns Confluent, the platform underneath is a single-vendor, IBM-supported stack — not a bolt-on at risk of losing support. The practice ships with:

- **Infrastructure-as-Code library** — production-hardened Terraform and Ansible for Confluent Platform on LinuxONE (supported on s390x from CP 8.2.0, including Confluent for Kubernetes and Flink/CMF), aligned with IBM's own IaC and OpenTelemetry direction for z17 operations
- **Sizing model** — a field-tested IFL sizing heuristic for broker and conduit workloads (GoodLabs IP; Confluent publishes no LinuxONE-specific sizing), I/O-DPU-aware for the z17 generation
- **Conduit decision framework** — the reference taxonomy for matching every source type to its correct on-ramp, with licensing and code-change implications pre-mapped
- **Reference architectures** — per-conduit patterns (MQ→CP, CDC→CP, zDIH→CP, Data Gate→CP) with the constraints baked in
- **Compliance mapping** — FIPS 140-3 crypto via CEX8S + BC-FIPS provider (with CP FIPS-mode sequencing on s390x scoped in the assessment, not assumed); confidential-computing placement via IBM Secure Execution; a quantum-safe-ready cryptographic envelope; DORA / operational-resilience alignment

## Why Now: the z17 Generation Changes the Math

- **In-transaction inference** (Telum II on-chip + Spyre accelerator) means AI-scored events at the source — streaming becomes the distribution layer for intelligence, not just data
- **The Telum II integrated I/O DPU** is expected to benefit broker throughput — reframing the "won't Kafka be slow on Z?" question around hardware I/O offload (we validate the per-workload delta in the assessment rather than asserting it)
- **Up to eight-nines platform availability (in clustered / GDPS configurations) + a quantum-safe-ready crypto envelope** put your streaming platform inside the same resilience and cryptographic envelope as the systems of record. The frame's availability *complements* Kafka's own replication guarantees (RF 3, `min.insync.replicas=2`) rather than replacing them — a compliance story, not just a latency one
- **Single-frame colocation** makes platform placement (on-IFL vs. rack-adjacent) a scoped decision in the assessment, not a religious argument

---

**GoodLabs Studio** — Mainframe Modernization Practice | Toronto · New York
*IBM Z / LinuxONE · Confluent · FSI*
