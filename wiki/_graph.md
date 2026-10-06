---
title: Concept Graph / Backlink Registry
last_updated: 2026-05-18
---

# Backlink Registry

Tracks which articles reference which. The LLM maintains this file.

## Format

```
[source article] → [target article] : relationship description
```

## Backlinks

concepts/confluent-cloud-certified-operator-exam → concepts/cc-cluster-tiers : Core Concepts domain refresher
concepts/confluent-cloud-certified-operator-exam → concepts/confluent-cloud-cluster-sku-selection : Static Operations domain refresher
concepts/confluent-cloud-certified-operator-exam → concepts/cluster-linking-topology : Resilience domain refresher
concepts/confluent-cloud-certified-operator-exam → concepts/schema-registry-best-practices : Data Governance domain refresher
concepts/confluent-cloud-certified-operator-exam → concepts/observability-metrics-mapping : Dynamic Operations domain refresher
concepts/confluent-cloud-certified-operator-exam → concepts/flink-confluent-cloud-setup : Streaming Pipelines domain refresher

concepts/fsi-data-streaming-platform → concepts/sla-tiers : tier system drives all governance defaults
concepts/fsi-data-streaming-platform → concepts/schema-evolution-strategies : schema governance for the platform
concepts/fsi-data-streaming-platform → concepts/fsi-compliance : compliance audit trail for CI/CD
concepts/fsi-data-streaming-platform → patterns/fsi-governance-automation : governance-as-code pattern
concepts/fsi-data-streaming-platform → patterns/dr-cluster-linking : CL DR for CC deployments
concepts/fsi-data-streaming-platform → patterns/dr-mirrormaker2 : MM2 DR for CFK/CP deployments
concepts/fsi-data-streaming-platform → patterns/dr-multi-region-cluster : MRC RPO=0 for CP
concepts/fsi-data-streaming-platform → patterns/topic-naming : naming convention
concepts/fsi-data-streaming-platform → synthesis/adr-index : architecture decisions

concepts/sla-tiers → concepts/fsi-data-streaming-platform : platform overview
concepts/sla-tiers → concepts/schema-evolution-strategies : compatibility modes derived from tier
concepts/sla-tiers → patterns/fsi-governance-automation : tiers propagate through IaC
concepts/sla-tiers → patterns/dr-cluster-linking : DR thresholds per tier
concepts/sla-tiers → patterns/dr-mirrormaker2 : MM2 lag monitoring per tier
concepts/sla-tiers → patterns/dr-multi-region-cluster : compliance tier drives RPO=0
concepts/sla-tiers → synthesis/adr-index : ADR-002, ADR-008

concepts/schema-evolution-strategies → concepts/sla-tiers : compatibility modes per tier
concepts/schema-evolution-strategies → patterns/topic-naming : version segment for breaking changes
concepts/schema-evolution-strategies → patterns/fsi-governance-automation : Terraform module enforcement
concepts/schema-evolution-strategies → concepts/fsi-compliance : audit trail for schema changes
concepts/schema-evolution-strategies → synthesis/adr-index : ADR-001, ADR-002

concepts/fsi-compliance → concepts/fsi-data-streaming-platform : platform context
concepts/fsi-compliance → patterns/fsi-governance-automation : CI/CD pattern producing audit trail
concepts/fsi-compliance → concepts/sla-tiers : tier definitions
concepts/fsi-compliance → concepts/schema-evolution-strategies : schema governance enforced by CI

patterns/fsi-governance-automation → concepts/fsi-data-streaming-platform : platform overview
patterns/fsi-governance-automation → concepts/sla-tiers : tier defaults
patterns/fsi-governance-automation → patterns/topic-naming : naming enforcement
patterns/fsi-governance-automation → concepts/schema-evolution-strategies : compatibility modes
patterns/fsi-governance-automation → concepts/fsi-compliance : audit trail

patterns/topic-naming → concepts/schema-evolution-strategies : versioned topic migration
patterns/topic-naming → patterns/fsi-governance-automation : module validates names
patterns/topic-naming → concepts/sla-tiers : tier selection per topic
patterns/topic-naming → synthesis/adr-index : ADR-007

patterns/dr-cluster-linking → patterns/dr-mirrormaker2 : alternative backend
patterns/dr-cluster-linking → patterns/dr-multi-region-cluster : RPO=0 alternative
patterns/dr-cluster-linking → concepts/sla-tiers : RPO/RTO targets per tier
patterns/dr-cluster-linking → concepts/cluster-linking-topology : CL architecture
patterns/dr-cluster-linking → synthesis/adr-index : ADR-003, ADR-005

patterns/dr-mirrormaker2 → patterns/dr-cluster-linking : alternative for CC
patterns/dr-mirrormaker2 → patterns/dr-multi-region-cluster : RPO=0 on CP
patterns/dr-mirrormaker2 → concepts/sla-tiers : tier-based RPO/RTO

patterns/dr-multi-region-cluster → patterns/dr-cluster-linking : async DR for CC
patterns/dr-multi-region-cluster → patterns/dr-mirrormaker2 : async DR for CFK/CP
patterns/dr-multi-region-cluster → concepts/sla-tiers : compliance tier requirement
patterns/dr-multi-region-cluster → synthesis/adr-index : ADR-005, ADR-008
patterns/dr-multi-region-cluster → patterns/yaml-topic-rbac-admin-tool : provisioning tool for MRC target topics/RBAC

patterns/yaml-topic-rbac-admin-tool → patterns/dr-multi-region-cluster : target topology for provisioned topics
patterns/yaml-topic-rbac-admin-tool → patterns/x86-to-linuxone-cluster-linking-migration : parallel audit/validate/evidence discipline
patterns/yaml-topic-rbac-admin-tool → patterns/fsi-governance-automation : governance-as-code substitute for CP (Terraform is Cloud-only)
patterns/yaml-topic-rbac-admin-tool → patterns/topic-naming : naming/config conventions for regenerated topic YAML
patterns/yaml-topic-rbac-admin-tool → concepts/sla-tiers : tier system drives placement-policy assignment
patterns/yaml-topic-rbac-admin-tool → patterns/cp-mrc-migration-rehearsal-rig : rehearsal rig for the migration this tool provisions topics/RBAC for

# Outbound — patterns/cp-mrc-migration-rehearsal-rig
patterns/cp-mrc-migration-rehearsal-rig → patterns/dr-multi-region-cluster : target architecture this rehearsal migrates toward
patterns/cp-mrc-migration-rehearsal-rig → patterns/x86-to-linuxone-cluster-linking-migration : runbook shape the Cluster Linking cutover follows
patterns/cp-mrc-migration-rehearsal-rig → patterns/yaml-topic-rbac-admin-tool : tool that handles the ACL/RBAC portability this rig skips
patterns/cp-mrc-migration-rehearsal-rig → concepts/sla-tiers : informs how aggressively to pursue the zero-DR-coverage mitigation
patterns/cp-mrc-migration-rehearsal-rig → patterns/shadowtraffic-confluent-cloud-datagen : ShadowTraffic producer config/flags used to generate the rig's live background traffic
patterns/dr-multi-region-cluster → patterns/cp-mrc-migration-rehearsal-rig : hands-on rehearsal of the live-absorption path into this architecture

patterns/fsi-governance-automation → patterns/yaml-topic-rbac-admin-tool : CP-side tool where Terraform provider can't reach MDS
patterns/x86-to-linuxone-cluster-linking-migration → patterns/yaml-topic-rbac-admin-tool : same audit discipline applied to topic/RBAC provisioning

synthesis/adr-index → concepts/fsi-data-streaming-platform : platform these decisions govern
synthesis/adr-index → concepts/sla-tiers : tier system (ADR-002, ADR-008)
synthesis/adr-index → concepts/schema-evolution-strategies : Avro and compatibility (ADR-001, ADR-002)
synthesis/adr-index → patterns/fsi-governance-automation : implements decisions
synthesis/adr-index → patterns/topic-naming : naming convention (ADR-007)
synthesis/adr-index → patterns/dr-cluster-linking : CL decision (ADR-005)
synthesis/adr-index → patterns/dr-mirrormaker2 : MM2 procedures
synthesis/adr-index → patterns/dr-multi-region-cluster : MRC RPO=0 (ADR-005, ADR-008)

patterns/latency-optimized-kafka-client → concepts/azure-connection-management : ILB silent-kill reference for Azure overlay
patterns/latency-optimized-kafka-client → patterns/low-latency-kafka-azure : Azure overlay bundling this baseline + ILB + rebalance avoidance
patterns/latency-optimized-kafka-client → patterns/producer-config-fsi : durability-first producer baseline this profile extends
patterns/latency-optimized-kafka-client → patterns/consumer-config-fsi : manual-commit consumer baseline this profile extends
patterns/latency-optimized-kafka-client → concepts/producer-batching-config : RecordAccumulator internals behind linger/batch
patterns/latency-optimized-kafka-client → concepts/consumer-group-rebalancing : KIP-429/345/848 rebalance protocol generations
patterns/latency-optimized-kafka-client → concepts/sla-tiers : FSI tier mapping for which workloads qualify

concepts/azure-connection-management → patterns/latency-optimized-kafka-client : cloud-agnostic baseline the Azure pattern overlays
patterns/low-latency-kafka-azure → patterns/latency-optimized-kafka-client : cross-cloud baseline this Azure pattern specializes
patterns/producer-config-fsi → patterns/latency-optimized-kafka-client : latency-tier override on top of the FSI producer baseline
patterns/consumer-config-fsi → patterns/latency-optimized-kafka-client : latency-tier override on top of the FSI consumer baseline

concepts/cluster-linking-topology → patterns/dr-cluster-linking : CL DR pattern using CL
concepts/cluster-linking-topology → concepts/fsi-data-streaming-platform : platform monitoring context
concepts/cluster-linking-topology → concepts/sla-tiers : RPO/RTO targets per tier

concepts/consumer-group-rebalancing → concepts/consumer-lag-monitoring : lag spikes during rebalances
concepts/consumer-group-rebalancing → concepts/exactly-once-semantics : rebalance impact on EOS
concepts/consumer-group-rebalancing → concepts/producer-batching-config : producer-side tuning
concepts/consumer-group-rebalancing → patterns/aks-kafka-tuning : static membership in Kubernetes, CooperativeStickyAssignor

concepts/consumer-lag-monitoring → concepts/consumer-group-rebalancing : rebalances cause lag spikes
concepts/consumer-lag-monitoring → concepts/sla-tiers : tier-based lag alert thresholds
concepts/consumer-lag-monitoring → concepts/fsi-data-streaming-platform : platform monitoring context

concepts/exactly-once-semantics → concepts/consumer-group-rebalancing : rebalance behavior during transactions
concepts/exactly-once-semantics → concepts/consumer-lag-monitoring : LSO-based lag under read_committed
concepts/exactly-once-semantics → patterns/fsi-exactly-once : regulatory reporting and audit for EOS
concepts/exactly-once-semantics → concepts/flink-checkpointing : checkpoint mechanics for Flink 2PC
concepts/exactly-once-semantics → concepts/producer-batching-config : batching interaction with idempotence

concepts/flink-checkpointing → concepts/exactly-once-semantics : end-to-end delivery guarantees
concepts/flink-checkpointing → concepts/consumer-lag-monitoring : offset commits feed consumer lag metrics

concepts/producer-batching-config → concepts/exactly-once-semantics : idempotence constraints on batching
concepts/producer-batching-config → concepts/consumer-lag-monitoring : downstream impact on e2e latency
concepts/producer-batching-config → patterns/aks-kafka-tuning : platform-specific producer tuning

patterns/aks-kafka-tuning → concepts/producer-batching-config : client-side tuning pairing
patterns/aks-kafka-tuning → concepts/fsi-data-streaming-platform : FSI architecture context
patterns/aks-kafka-tuning → concepts/sla-tiers : latency tiers drive VM/storage selection
patterns/aks-kafka-tuning → patterns/dr-cluster-linking : cross-region replication
patterns/aks-kafka-tuning → concepts/consumer-lag-monitoring : monitoring patterns

patterns/dead-letter-queue-design → concepts/exactly-once-semantics : DLQ interaction with transactions
patterns/dead-letter-queue-design → concepts/consumer-group-rebalancing : rebalance during retry backoff
patterns/dead-letter-queue-design → patterns/fsi-exactly-once : FSI failure handling requirements
patterns/dead-letter-queue-design → patterns/topic-naming : naming conventions for DLQ topics
patterns/dead-letter-queue-design → concepts/consumer-lag-monitoring : DLQ consumer lag monitoring

patterns/fsi-exactly-once → concepts/exactly-once-semantics : foundational EOS mechanisms
patterns/fsi-exactly-once → concepts/sla-tiers : tier definitions for EOS requirements
patterns/fsi-exactly-once → concepts/fsi-data-streaming-platform : overall FSI architecture
patterns/fsi-exactly-once → patterns/dead-letter-queue-design : error handling complementing EOS
patterns/fsi-exactly-once → patterns/dr-cluster-linking : DR with EOS implications

concepts/linuxone-kafka-integration → concepts/fsi-data-streaming-platform : platform overview including LinuxONE context
concepts/linuxone-kafka-integration → concepts/sla-tiers : latency tiers (market_data, risk) drive LinuxONE adoption
concepts/linuxone-kafka-integration → concepts/fsi-compliance : FIPS 140-2 and audit trail requirements
concepts/linuxone-kafka-integration → patterns/dr-cluster-linking : DR pattern for LinuxONE-produced topics

patterns/audit-log-siem-integration → concepts/fsi-data-streaming-platform : observability templates cover operational metrics; audit log is the security complement
patterns/audit-log-siem-integration → concepts/fsi-compliance : audit trail for regulatory frameworks
patterns/audit-log-siem-integration → concepts/consumer-lag-monitoring : operational metrics monitoring (other half of observability)
patterns/audit-log-siem-integration → patterns/fsi-exactly-once : audit logging requirements for transactional processing

patterns/low-latency-kafka-azure → concepts/sla-tiers : sub-100ms latency tier framing
patterns/low-latency-kafka-azure → concepts/fsi-data-streaming-platform : Azure deployment model context
patterns/low-latency-kafka-azure → concepts/consumer-group-rebalancing : cooperative-sticky + static membership rationale
patterns/low-latency-kafka-azure → concepts/producer-batching-config : latency-favored tuning (linger.ms=0, batch.size=16384, compression=none)
patterns/low-latency-kafka-azure → patterns/aks-kafka-tuning : Azure-specific deployment patterns
patterns/low-latency-kafka-azure → patterns/dr-cluster-linking : DR pattern compatible with this client profile
patterns/low-latency-kafka-azure → concepts/azure-connection-management : Layer 2 ILB-aware connection management (canonical reference)

concepts/azure-connection-management → patterns/low-latency-kafka-azure : the named profile that bundles this with latency tuning
concepts/azure-connection-management → patterns/aks-kafka-tuning : broker-side context for AKS-hosted clusters
concepts/azure-connection-management → concepts/confluent-cloud-private-networking : PrivateLink as architectural bypass for ILB silent kill
concepts/azure-connection-management → concepts/network-connectivity-by-tier : tier-to-mode mapping for Confluent Cloud
concepts/azure-connection-management → concepts/producer-batching-config : adjacent client config (throughput vs lifecycle separation)

patterns/aks-kafka-tuning → concepts/azure-connection-management : canonical reference for the ILB client mitigation table

concepts/confluent-cloud-private-networking → concepts/azure-connection-management : ILB silent-kill is what PrivateLink bypasses

patterns/producer-config-fsi → concepts/producer-batching-config : batching internals
patterns/producer-config-fsi → concepts/exactly-once-semantics : idempotent + transactional producer mechanics
patterns/producer-config-fsi → patterns/fsi-exactly-once : producer layer of five-layer EOS
patterns/producer-config-fsi → patterns/low-latency-kafka-azure : sub-100ms overlay
patterns/producer-config-fsi → concepts/schema-registry-best-practices : auto.register policy and CI
patterns/producer-config-fsi → patterns/topic-naming : naming canon for keyed topics
patterns/producer-config-fsi → synthesis/confluent-gotchas-top-20 : producer-specific gotchas

patterns/consumer-config-fsi → concepts/consumer-group-rebalancing : eager/cooperative/KIP-848 protocols
patterns/consumer-config-fsi → concepts/consumer-lag-monitoring : offset and time lag, CC Metrics API
patterns/consumer-config-fsi → concepts/exactly-once-semantics : read_committed isolation
patterns/consumer-config-fsi → patterns/producer-config-fsi : paired producer baseline
patterns/consumer-config-fsi → patterns/low-latency-kafka-azure : fraud-tier overlay
patterns/consumer-config-fsi → patterns/dead-letter-queue-design : poison-pill routing
patterns/consumer-config-fsi → synthesis/confluent-gotchas-top-20 : consumer-specific gotchas

concepts/cc-cluster-tiers → concepts/network-connectivity-by-tier : networking mapped to tier
concepts/cc-cluster-tiers → patterns/dr-cluster-linking : tier requirements for CL source
concepts/cc-cluster-tiers → concepts/fsi-data-streaming-platform : platform overview / six deployment models
concepts/cc-cluster-tiers → concepts/sla-tiers : FSI SLA tiers vs CC cluster tiers (naming overlap)
concepts/cc-cluster-tiers → synthesis/confluent-gotchas-top-20 : gotcha #7 (RF/min.insync/unclean fixed)

concepts/schema-registry-best-practices → concepts/schema-evolution-strategies : tier-based compatibility policy
concepts/schema-registry-best-practices → patterns/fsi-governance-automation : Terraform enforcement of compat
concepts/schema-registry-best-practices → patterns/topic-naming : versioned-topic exception (ADR-007)
concepts/schema-registry-best-practices → patterns/producer-config-fsi : auto.register.schemas=false enforcement
concepts/schema-registry-best-practices → concepts/fsi-compliance : schema-change audit trail
concepts/schema-registry-best-practices → synthesis/confluent-gotchas-top-20 : gotchas #8, #9, #10

patterns/connect-deployment-models → patterns/dead-letter-queue-design : DLQ topic design
patterns/connect-deployment-models → concepts/exactly-once-semantics : KIP-618 EOS source
patterns/connect-deployment-models → patterns/fsi-governance-automation : Terraform connector deployment
patterns/connect-deployment-models → patterns/fsi-exactly-once : outbox/upsert as consumer-side EOS
patterns/connect-deployment-models → concepts/schema-registry-best-practices : converter/SR config
patterns/connect-deployment-models → synthesis/confluent-gotchas-top-20 : gotchas #11, #12, #13

patterns/flink-runtime-models → concepts/flink-checkpointing : checkpoint mechanics on CMF
patterns/flink-runtime-models → patterns/linuxone-flink-validation-tuning : CMF on s390x
patterns/flink-runtime-models → concepts/exactly-once-semantics : Flink two-phase commit
patterns/flink-runtime-models → concepts/schema-registry-best-practices : Flink reads SR automatically
patterns/flink-runtime-models → synthesis/confluent-gotchas-top-20 : gotchas #14, #15, #16

concepts/network-connectivity-by-tier → concepts/cc-cluster-tiers : tier matrix extended on networking axis
concepts/network-connectivity-by-tier → patterns/dr-cluster-linking : Consul endpoint flip, CC↔CC private
concepts/network-connectivity-by-tier → patterns/low-latency-kafka-azure : ILB-aware, fetch-from-follower
concepts/network-connectivity-by-tier → patterns/aks-kafka-tuning : advertised listeners on CFK
concepts/network-connectivity-by-tier → synthesis/confluent-gotchas-top-20 : gotchas #18, #20
concepts/network-connectivity-by-tier → concepts/confluent-cloud-private-networking : deep dive on PrivateLink Gateway mechanics

concepts/confluent-cloud-private-networking → concepts/network-connectivity-by-tier : tier-to-mode mapping (parent article)
concepts/confluent-cloud-private-networking → concepts/cc-cluster-tiers : Enterprise vs Dedicated tier requirements
concepts/confluent-cloud-private-networking → patterns/dr-cluster-linking : CL over private, CC↔CP reachability planning
concepts/confluent-cloud-private-networking → patterns/low-latency-kafka-azure : Azure ILB connection-management for self-managed paths
concepts/confluent-cloud-private-networking → concepts/fsi-data-streaming-platform : six deployment models context

synthesis/confluent-gotchas-top-20 → patterns/producer-config-fsi : producer gotchas resolution
synthesis/confluent-gotchas-top-20 → patterns/consumer-config-fsi : consumer gotchas resolution
synthesis/confluent-gotchas-top-20 → concepts/cc-cluster-tiers : tier-specific gotchas
synthesis/confluent-gotchas-top-20 → concepts/schema-registry-best-practices : schema gotchas
synthesis/confluent-gotchas-top-20 → concepts/schema-evolution-strategies : compatibility direction gotcha
synthesis/confluent-gotchas-top-20 → patterns/connect-deployment-models : Connect gotchas
synthesis/confluent-gotchas-top-20 → patterns/flink-runtime-models : Flink gotchas
synthesis/confluent-gotchas-top-20 → concepts/network-connectivity-by-tier : networking gotchas
synthesis/confluent-gotchas-top-20 → concepts/consumer-group-rebalancing : rebalance gotcha context
synthesis/confluent-gotchas-top-20 → patterns/fsi-exactly-once : outbox/idempotent-consumer for EOS into a DB

patterns/schema-registry-shared-types → concepts/schema-registry-best-practices : operational surface (subject strategy, ID portability, references API)
patterns/schema-registry-shared-types → concepts/schema-evolution-strategies : compatibility-by-tier and evolution runbook
patterns/schema-registry-shared-types → patterns/topic-naming : domain naming convention
patterns/schema-registry-shared-types → patterns/fsi-governance-automation : Terraform registers shared types before referencing subjects
patterns/schema-registry-shared-types → concepts/fsi-compliance : schema-change audit trail

concepts/schema-registry-best-practices → patterns/schema-registry-shared-types : shared-types library pattern using references
concepts/schema-evolution-strategies → patterns/schema-registry-shared-types : shared-types library example of FULL_TRANSITIVE in practice

concepts/flink-confluent-cloud-setup → patterns/flink-runtime-models : cross-runtime defaults (watermarks, state-ttl, upsert-kafka) and compute-pool sizing
concepts/flink-confluent-cloud-setup → concepts/flink-checkpointing : Chandy-Lamport mechanics (fully managed on CC)
concepts/flink-confluent-cloud-setup → concepts/schema-evolution-strategies : tier-based compatibility selection (FULL/FULL_TRANSITIVE for Flink)
concepts/flink-confluent-cloud-setup → concepts/schema-registry-best-practices : TopicNameStrategy + operational surface
concepts/flink-confluent-cloud-setup → concepts/exactly-once-semantics : Flink two-phase commit foundation
concepts/flink-confluent-cloud-setup → concepts/fsi-compliance : audit-log requirements for production service accounts

patterns/flink-runtime-models → concepts/flink-confluent-cloud-setup : CC-specific setup deep dive (compute pools, RBAC, lifecycle)
concepts/flink-checkpointing → concepts/flink-confluent-cloud-setup : CC managed checkpointing context
concepts/schema-evolution-strategies → concepts/flink-confluent-cloud-setup : statement evolution and carry-over offsets
concepts/schema-registry-best-practices → concepts/flink-confluent-cloud-setup : Flink reads/writes SR subjects under dual-plane RBAC

## H.1 — confluent-agent-skills ingest (2026-05-16)

# Parent #1: kafka-streams-topology-patterns — outbound
patterns/kafka-streams-topology-patterns → concepts/exactly-once-semantics : EOS implications for stateful topologies
patterns/kafka-streams-topology-patterns → concepts/consumer-group-rebalancing : rebalance behavior under stateful operators
patterns/kafka-streams-topology-patterns → concepts/kafka-streams-architecture : architecture context for topology choices
patterns/kafka-streams-topology-patterns → concepts/kafka-streams-debugging : debugging stateful topologies

# Parent #2: kafka-streams-debugging — outbound
concepts/kafka-streams-debugging → concepts/kafka-streams-production-hardening : production diagnostics complement
concepts/kafka-streams-debugging → concepts/kafka-streams-4x-uncaught-exception-handler-import : trip-wire on KS 4.x import
concepts/kafka-streams-debugging → concepts/avro-schema-source-directory : trip-wire on Avro source dir
concepts/kafka-streams-debugging → concepts/schema-aware-console-producer-required : trip-wire on console-producer verification
concepts/kafka-streams-debugging → synthesis/confluent-gotchas-top-20 : cross-pollination with gotchas index

# Parent #3: kafka-streams-production-hardening — outbound
concepts/kafka-streams-production-hardening → concepts/exactly-once-semantics : EOS production posture
concepts/kafka-streams-production-hardening → patterns/fsi-exactly-once : FSI five-layer EOS pattern
concepts/kafka-streams-production-hardening → concepts/exactly-once-v2-warpstream-throughput-cost : trip-wire on EOS cost on WarpStream
concepts/kafka-streams-production-hardening → concepts/kafka-streams-debugging : debugging counterpart
concepts/kafka-streams-production-hardening → patterns/producer-config-fsi : producer-layer config baseline

# Parent #4: kafka-streams-schema-patterns — outbound
concepts/kafka-streams-schema-patterns → concepts/schema-registry-best-practices : SR operational surface
concepts/kafka-streams-schema-patterns → concepts/schema-evolution-strategies : compatibility policy
concepts/kafka-streams-schema-patterns → patterns/schema-registry-shared-types : shared-types library pattern
concepts/kafka-streams-schema-patterns → concepts/avro-schema-source-directory : trip-wire on Avro source dir

# Parent #5: kafka-streams-config-baseline — outbound
concepts/kafka-streams-config-baseline → patterns/producer-config-fsi : producer baseline pairing
concepts/kafka-streams-config-baseline → patterns/consumer-config-fsi : consumer baseline pairing
concepts/kafka-streams-config-baseline → concepts/warpstream-config-overrides : trip-wire on WarpStream config drift
concepts/kafka-streams-config-baseline → concepts/kafka-streams-architecture : architectural rationale for defaults

# Parent #6: kafka-streams-architecture — outbound
concepts/kafka-streams-architecture → concepts/exactly-once-semantics : EOS in stream processing
concepts/kafka-streams-architecture → concepts/flink-checkpointing : alternative streaming runtime context
concepts/kafka-streams-architecture → patterns/flink-runtime-models : Flink vs Kafka Streams runtime trade-offs
concepts/kafka-streams-architecture → concepts/fsi-data-streaming-platform : platform context

# Parent #7: cdc-to-tableflow-flink-decode — outbound
patterns/cdc-to-tableflow-flink-decode → concepts/tableflow-changelog-mode-immutability : trip-wire on Tableflow immutability
patterns/cdc-to-tableflow-flink-decode → patterns/cdc-tableflow-flink-decode-required : trip-wire elaborating decode requirement
patterns/cdc-to-tableflow-flink-decode → concepts/cdc-source-connector-setup : pre-pipeline connector setup
patterns/cdc-to-tableflow-flink-decode → concepts/flink-checkpointing : checkpointing for the Flink decode step
patterns/cdc-to-tableflow-flink-decode → concepts/flink-confluent-cloud-setup : CC Flink setup context
patterns/cdc-to-tableflow-flink-decode → concepts/exactly-once-semantics : EOS across the pipeline

# Parent #8: cdc-source-connector-setup — outbound
concepts/cdc-source-connector-setup → patterns/cdc-to-tableflow-flink-decode : operational counterpart pattern
concepts/cdc-source-connector-setup → concepts/oracle-xstream-source-limitations : trip-wire on after.state.only
concepts/cdc-source-connector-setup → patterns/connect-deployment-models : Connect deployment patterns

# Parent #9: schema-registry-adoption-playbook — outbound
patterns/schema-registry-adoption-playbook → concepts/schema-registry-best-practices : operational surface for SR
patterns/schema-registry-adoption-playbook → concepts/schema-evolution-strategies : compatibility policy
patterns/schema-registry-adoption-playbook → patterns/fsi-governance-automation : Terraform enforcement of registered subjects
patterns/schema-registry-adoption-playbook → patterns/schema-registry-shared-types : shared-types library
patterns/schema-registry-adoption-playbook → concepts/schema-inference-and-pii-categorization : inference + PII tagging sibling

# Parent #10: schema-inference-and-pii-categorization — outbound
concepts/schema-inference-and-pii-categorization → concepts/schema-registry-best-practices : SR operational surface
concepts/schema-inference-and-pii-categorization → concepts/fsi-compliance : PII categorization connects to compliance
concepts/schema-inference-and-pii-categorization → patterns/schema-registry-shared-types : shared types include PII-tagged fields
concepts/schema-inference-and-pii-categorization → patterns/schema-registry-adoption-playbook : adoption playbook sibling

# Inbound (existing wiki → new H.1 articles) — backfill so every new article has ≥1 inbound
concepts/exactly-once-semantics → concepts/kafka-streams-production-hardening : EOS production application
concepts/exactly-once-semantics → concepts/kafka-streams-architecture : EOS in stream processing
concepts/schema-registry-best-practices → concepts/kafka-streams-schema-patterns : KS-specific schema patterns
concepts/schema-registry-best-practices → patterns/schema-registry-adoption-playbook : adoption playbook for SR
concepts/schema-registry-best-practices → concepts/schema-inference-and-pii-categorization : inference + PII categorization
patterns/connect-deployment-models → concepts/cdc-source-connector-setup : CDC source connector deployment specifics
concepts/flink-checkpointing → patterns/cdc-to-tableflow-flink-decode : checkpointing in the CDC decode pipeline
patterns/producer-config-fsi → concepts/kafka-streams-config-baseline : KS-specific config baseline
patterns/consumer-config-fsi → concepts/kafka-streams-config-baseline : KS-specific config baseline
synthesis/confluent-gotchas-top-20 → concepts/kafka-streams-debugging : debugging-focused gotchas
patterns/kafka-streams-topology-patterns → concepts/schema-registry-best-practices : SR operational surface for KS state
concepts/kafka-streams-config-baseline → concepts/exactly-once-semantics : EOS configuration anchor
concepts/kafka-streams-architecture → patterns/kafka-streams-topology-patterns : runtime model that informs topology choices
concepts/kafka-streams-debugging → patterns/kafka-streams-topology-patterns : debugging counterpart for topology patterns
concepts/kafka-streams-production-hardening → patterns/kafka-streams-topology-patterns : production posture for EOS topology decisions

# Trip-wires — outbound (close forward-references from H.1-02 parents)
# Trip-wire #1: tableflow-changelog-mode-immutability
concepts/tableflow-changelog-mode-immutability → patterns/cdc-to-tableflow-flink-decode : parent ingest article (back-link per D-06)
concepts/tableflow-changelog-mode-immutability → patterns/cdc-tableflow-flink-decode-required : sibling trip-wire (Tableflow + CDC)
concepts/tableflow-changelog-mode-immutability → concepts/oracle-xstream-source-limitations : sibling trip-wire (CDC-Tableflow cluster)

# Trip-wire #2: cdc-tableflow-flink-decode-required
patterns/cdc-tableflow-flink-decode-required → patterns/cdc-to-tableflow-flink-decode : parent ingest article (back-link per D-06)
patterns/cdc-tableflow-flink-decode-required → concepts/tableflow-changelog-mode-immutability : sibling trip-wire
patterns/cdc-tableflow-flink-decode-required → concepts/cdc-source-connector-setup : parent for CDC connector configs

# Trip-wire #3: oracle-xstream-source-limitations
concepts/oracle-xstream-source-limitations → concepts/cdc-source-connector-setup : parent ingest article (back-link per D-06)
concepts/oracle-xstream-source-limitations → concepts/tableflow-changelog-mode-immutability : sibling trip-wire (CDC-Tableflow cluster)
concepts/oracle-xstream-source-limitations → patterns/cdc-tableflow-flink-decode-required : sibling trip-wire (decode pattern obviates after.state.only shortcuts)

# Trip-wire #4: kafka-streams-4x-uncaught-exception-handler-import
concepts/kafka-streams-4x-uncaught-exception-handler-import → concepts/kafka-streams-debugging : parent ingest article (back-link per D-06)
concepts/kafka-streams-4x-uncaught-exception-handler-import → concepts/kafka-streams-production-hardening : closely-related parent (Layer 4 error handling)
concepts/kafka-streams-4x-uncaught-exception-handler-import → concepts/avro-schema-source-directory : sibling KS-programming trip-wire
concepts/kafka-streams-4x-uncaught-exception-handler-import → concepts/schema-aware-console-producer-required : sibling KS-programming trip-wire

# Trip-wire #5: avro-schema-source-directory
concepts/avro-schema-source-directory → concepts/kafka-streams-debugging : parent ingest article (back-link per D-06)
concepts/avro-schema-source-directory → concepts/kafka-streams-schema-patterns : parent for schema-patterns context
concepts/avro-schema-source-directory → concepts/kafka-streams-4x-uncaught-exception-handler-import : sibling KS-programming trip-wire

# Trip-wire #6: schema-aware-console-producer-required
concepts/schema-aware-console-producer-required → concepts/schema-registry-best-practices : SR operational surface
concepts/schema-aware-console-producer-required → concepts/kafka-streams-debugging : parent ingest article (back-link per D-06)
concepts/schema-aware-console-producer-required → concepts/kafka-streams-4x-uncaught-exception-handler-import : sibling KS-programming trip-wire

# Trip-wire #7: warpstream-schema-registry-format-constraint
concepts/warpstream-schema-registry-format-constraint → concepts/schema-registry-best-practices : SR operational surface
concepts/warpstream-schema-registry-format-constraint → concepts/warpstream-config-overrides : sibling WarpStream trip-wire
concepts/warpstream-schema-registry-format-constraint → concepts/exactly-once-v2-warpstream-throughput-cost : sibling WarpStream trip-wire

# Trip-wire #8: warpstream-config-overrides
concepts/warpstream-config-overrides → concepts/kafka-streams-config-baseline : parent ingest article (back-link per D-06)
concepts/warpstream-config-overrides → concepts/warpstream-schema-registry-format-constraint : sibling WarpStream trip-wire
concepts/warpstream-config-overrides → concepts/exactly-once-v2-warpstream-throughput-cost : sibling WarpStream trip-wire

# Trip-wire #9: exactly-once-v2-warpstream-throughput-cost
concepts/exactly-once-v2-warpstream-throughput-cost → concepts/exactly-once-semantics : EOS foundation
concepts/exactly-once-v2-warpstream-throughput-cost → concepts/kafka-streams-production-hardening : parent ingest article (back-link per D-06)
concepts/exactly-once-v2-warpstream-throughput-cost → concepts/warpstream-config-overrides : sibling WarpStream trip-wire
concepts/exactly-once-v2-warpstream-throughput-cost → concepts/warpstream-schema-registry-format-constraint : sibling WarpStream trip-wire

## H.3a — FSI canon overlay for streaming-skills-plugin (2026-05-17)

# Outbound (overlay article → wiki articles it depends on / references)
patterns/fsi-canon-overlay-for-confluent-skills → concepts/exactly-once-semantics : EOS foundation for kafka-streams + python-client override rows (processing.guarantee, enable.idempotence)
patterns/fsi-canon-overlay-for-confluent-skills → concepts/schema-registry-best-practices : SR operational surface for kafka-schema-registry section overrides (TopicNameStrategy, BACKWARD/FULL compatibility)
patterns/fsi-canon-overlay-for-confluent-skills → concepts/schema-evolution-strategies : compatibility-mode policy underpinning the kafka-schema-registry section
patterns/fsi-canon-overlay-for-confluent-skills → patterns/topic-naming : <domain>.<entity>.<event> convention referenced in kafka-streams-programming override row
patterns/fsi-canon-overlay-for-confluent-skills → patterns/cdc-to-tableflow-flink-decode : decode pattern that the confluent-cloud-cdc-tableflow section inherits from upstream Critical Architecture Rule #1
patterns/fsi-canon-overlay-for-confluent-skills → patterns/fsi-l1-reference-architecture : Iceberg + CC Tableflow → Databricks analytics flow cited in the Tableflow destination override row

# Inbound (existing wiki articles → overlay) — 3 inbound to satisfy graph rule + ride existing high-density patterns
patterns/fsi-governance-automation → patterns/fsi-canon-overlay-for-confluent-skills : FSI operator overlay companion; governance-automation enforces canon via Terraform, overlay applies canon when upstream skills generate code
patterns/fsi-exactly-once → patterns/fsi-canon-overlay-for-confluent-skills : kafka-streams + python-client overlay sections cite the same producer/EOS canon as the five-layer FSI EOS pattern
patterns/topic-naming → patterns/fsi-canon-overlay-for-confluent-skills : naming-convention canon row in the kafka-streams-programming section enforces topic-naming pattern at scaffold time

## tableflow-iceberg-delta concept (2026-05-18)

# Outbound (concept article → wiki articles it depends on)
concepts/tableflow-iceberg-delta → patterns/cdc-to-tableflow-flink-decode : canonical CDC pipeline that lands in Tableflow
concepts/tableflow-iceberg-delta → concepts/tableflow-changelog-mode-immutability : trip-wire on first-materialization mode locking
concepts/tableflow-iceberg-delta → patterns/cdc-tableflow-flink-decode-required : trip-wire elaborating the decode requirement
concepts/tableflow-iceberg-delta → concepts/schema-registry-best-practices : SR compatibility drives Tableflow's schema-evolution behavior
concepts/tableflow-iceberg-delta → patterns/fsi-l1-reference-architecture : Cluster Linking → CC Tableflow → Databricks analytical bridge
concepts/tableflow-iceberg-delta → concepts/network-connectivity-by-tier : PrivateLink context for source CC clusters

# Inbound (existing wiki → new concept) — backfill to satisfy ≥1 inbound graph rule
patterns/cdc-to-tableflow-flink-decode → concepts/tableflow-iceberg-delta : framework-level concept for the destination of the decode pattern
concepts/tableflow-changelog-mode-immutability → concepts/tableflow-iceberg-delta : framework-level concept underpinning the trip-wire
patterns/fsi-l1-reference-architecture → concepts/tableflow-iceberg-delta : Tableflow is the operational→analytical bridge in the L1 architecture

## confluent-gateway concept (2026-05-18)

# Outbound (concept article → wiki articles it depends on)
concepts/confluent-gateway → concepts/confluent-cloud-private-networking : disambiguation — CC PrivateLink Gateway is a networking resource, not a protocol proxy
concepts/confluent-gateway → patterns/dr-cluster-linking : data-plane replication paired with gateway for client-side switchover
concepts/confluent-gateway → patterns/dr-mirrormaker2 : alternative replication backend for CFK/CP topologies fronted by the gateway
concepts/confluent-gateway → concepts/cluster-linking-topology : CL topology determines which switchover model applies
concepts/confluent-gateway → concepts/network-connectivity-by-tier : where the gateway sits relative to CC tier networking
concepts/confluent-gateway → patterns/audit-log-siem-integration : forward gateway audit events alongside broker audit logs

# Inbound (existing wiki → new concept) — backfill to satisfy ≥1 inbound graph rule
concepts/confluent-cloud-private-networking → concepts/confluent-gateway : sibling — protocol-proxy gateway distinct from PrivateLink Gateway
patterns/dr-cluster-linking → concepts/confluent-gateway : client-side switchover companion for sub-minute RTO
patterns/dr-mirrormaker2 → concepts/confluent-gateway : client-side switchover companion for CFK/CP DR

## dr-application-routing pattern (2026-05-18)

# Outbound (pattern article → wiki articles it depends on)
patterns/dr-application-routing → concepts/confluent-gateway : Solution 2 product (protocol-aware proxy)
patterns/dr-application-routing → patterns/dr-cluster-linking : data-plane replication this pattern routes clients across
patterns/dr-application-routing → patterns/dr-mirrormaker2 : alternative data-plane backend for CFK/CP
patterns/dr-application-routing → patterns/dr-multi-region-cluster : RPO=0 alternative when stateful correctness is non-negotiable
patterns/dr-application-routing → concepts/cluster-linking-topology : CL topology determines which routing model applies
patterns/dr-application-routing → concepts/sla-tiers : tier-based RTO targets drive routing-solution choice

# Inbound (existing wiki → new pattern) — backfill to satisfy ≥1 inbound graph rule
concepts/confluent-gateway → patterns/dr-application-routing : routing-pattern view of the gateway's DR use case
patterns/dr-cluster-linking → patterns/dr-application-routing : client-plane companion to CL data-plane DR
patterns/dr-mirrormaker2 → patterns/dr-application-routing : client-plane companion to MM2 data-plane DR

## kafka-connect-deployment-models concept (2026-05-18)

# Outbound (concept article → wiki articles it depends on)
concepts/kafka-connect-deployment-models → patterns/connect-deployment-models : operational counterpart pattern (decision matrix, tuning, triage)
concepts/kafka-connect-deployment-models → patterns/dead-letter-queue-design : DLQ topic design
concepts/kafka-connect-deployment-models → concepts/exactly-once-semantics : KIP-618 source EOS at the framework boundary
concepts/kafka-connect-deployment-models → concepts/schema-registry-best-practices : converter pipeline integrates SR
concepts/kafka-connect-deployment-models → concepts/cdc-source-connector-setup : source-connector lifecycle context for CDC
concepts/kafka-connect-deployment-models → concepts/network-connectivity-by-tier : Custom Connector + PrivateLink interaction
concepts/kafka-connect-deployment-models → patterns/fsi-canon-overlay-for-confluent-skills : vendor-consolidation rule driving fully-managed FSI default

# Inbound (existing wiki → new concept) — backfill to satisfy ≥1 inbound graph rule
patterns/connect-deployment-models → concepts/kafka-connect-deployment-models : framework-level concept underpinning the pattern
concepts/cdc-source-connector-setup → concepts/kafka-connect-deployment-models : source-connector framework architecture
concepts/exactly-once-semantics → concepts/kafka-connect-deployment-models : KIP-618 source EOS context

## oic-kafka-integration concept (2026-05-18)

# Outbound (concept article → wiki articles it depends on)
concepts/oic-kafka-integration → concepts/producer-batching-config : linger/batch/compression internals for cross-cloud overrides
concepts/oic-kafka-integration → concepts/azure-connection-management : ILB silent-kill applies to OIC Connectivity Agent socket
concepts/oic-kafka-integration → patterns/producer-config-fsi : canon producer baseline that OIC overrides extend
concepts/oic-kafka-integration → patterns/fsi-exactly-once : EOS implications when OIC adapter transactional support is uncertain
concepts/oic-kafka-integration → concepts/cc-cluster-tiers : per-tier capacity bounds OIC throughput
concepts/oic-kafka-integration → concepts/exactly-once-semantics : idempotent producer mechanics + ProducerFenced surface
concepts/oic-kafka-integration → concepts/confluent-cloud-private-networking : PrivateLink as architectural bypass for ILB hop

# Inbound (existing wiki → new concept) — backfill to satisfy ≥1 inbound graph rule
concepts/azure-connection-management → concepts/oic-kafka-integration : cross-cloud iPaaS instance of the ILB silent-kill problem
patterns/producer-config-fsi → concepts/oic-kafka-integration : OIC-specific cross-cloud overrides on the FSI producer baseline
concepts/producer-batching-config → concepts/oic-kafka-integration : cross-cloud RTT instance of the timeout-chain trade-off

## confluent-cloud-cluster-sku-selection concept (2026-05-18)

# Outbound (concept article → wiki articles it depends on)
concepts/confluent-cloud-cluster-sku-selection → concepts/cc-cluster-tiers : tier matrix this selection workflow routes into
concepts/confluent-cloud-cluster-sku-selection → concepts/network-connectivity-by-tier : networking axis orthogonal to SKU
concepts/confluent-cloud-cluster-sku-selection → concepts/confluent-cloud-private-networking : PrivateLink Gateway / PSC / PNI provisioning workflow
concepts/confluent-cloud-cluster-sku-selection → concepts/fsi-data-streaming-platform : six deployment models context
concepts/confluent-cloud-cluster-sku-selection → concepts/sla-tiers : multi-zone and RPO/RTO posture driven by FSI SLA tier
concepts/confluent-cloud-cluster-sku-selection → patterns/dr-cluster-linking : SKU constraints on CL source vs destination

# Inbound (existing wiki → new concept) — backfill to satisfy ≥1 inbound graph rule
concepts/cc-cluster-tiers → concepts/confluent-cloud-cluster-sku-selection : selection workflow on top of the tier matrix
concepts/network-connectivity-by-tier → concepts/confluent-cloud-cluster-sku-selection : SKU/networking orthogonality
concepts/fsi-data-streaming-platform → concepts/confluent-cloud-cluster-sku-selection : CC SKU selection within the platform's six deployment models

## ksqldb-observability concept (2026-05-20)

# Outbound (concept article → wiki articles it depends on)
concepts/ksqldb-observability → concepts/observability-metrics-mapping : cross-provider query syntax for ksqlDB metrics
concepts/ksqldb-observability → concepts/fsi-data-streaming-platform : ksqlDB as a platform component
concepts/ksqldb-observability → concepts/consumer-lag-monitoring : ksqlDB queries are consumers; commit lag overlaps
concepts/ksqldb-observability → concepts/kafka-streams-architecture : runtime model under every persistent query
concepts/ksqldb-observability → concepts/kafka-streams-debugging : diagnostic counterpart for stuck queries
concepts/ksqldb-observability → patterns/dead-letter-queue-design : deserialization-error DLQ pattern
concepts/ksqldb-observability → concepts/sla-tiers : alert thresholds per FSI tier
concepts/ksqldb-observability → patterns/producer-config-fsi : sink write reliability config

# Inbound (existing wiki → ksqldb-observability)
concepts/observability-metrics-mapping → concepts/ksqldb-observability : ksqlDB-specific column in the cross-provider spine
concepts/kafka-streams-architecture → concepts/ksqldb-observability : ksqlDB runs on Streams; observability inherits the MBean tree
concepts/consumer-lag-monitoring → concepts/ksqldb-observability : ksqlDB committed_offset_lag is a specialized consumer-lag instance

## cluster-linking-observability pattern (2026-05-20)

# Outbound (pattern article → wiki articles it depends on)
patterns/cluster-linking-observability → patterns/dr-cluster-linking : operational CL pattern that this article instruments
patterns/cluster-linking-observability → patterns/dr-mirrormaker2 : alternative replication backend (different obs surface)
patterns/cluster-linking-observability → patterns/cfk-observability-baseline : host platform for self-managed CL observability
patterns/cluster-linking-observability → concepts/confluent-platform-broker-jmx : JMX reference for CP self-managed CL fetcher lag
patterns/cluster-linking-observability → concepts/observability-metrics-mapping : cross-provider query syntax for CL metrics
patterns/cluster-linking-observability → concepts/sla-tiers : tier-to-RPO/RTO threshold mapping
patterns/cluster-linking-observability → concepts/exactly-once-semantics : EOS-on-CL caveat
patterns/cluster-linking-observability → patterns/fsi-l1-reference-architecture : DR consumed by CL → CC Tableflow → Databricks bridge

# Inbound (existing wiki → CL observability)
patterns/dr-cluster-linking → patterns/cluster-linking-observability : observability companion to the DR operational pattern
patterns/dr-mirrormaker2 → patterns/cluster-linking-observability : comparison anchor for the MM2 obs alternative
patterns/cfk-observability-baseline → patterns/cluster-linking-observability : DR-specific extension of the K8s observability stack
concepts/observability-metrics-mapping → patterns/cluster-linking-observability : DR-tier consumer of the cross-provider mirror lag query
concepts/cluster-linking-topology → patterns/cluster-linking-observability : topology choices the dashboards visualize

## cfk-observability-baseline pattern (2026-05-20)

# Outbound (pattern article → wiki articles it depends on)
patterns/cfk-observability-baseline → patterns/aks-kafka-tuning : Azure-specific broker tuning monitored by this stack
patterns/cfk-observability-baseline → concepts/confluent-platform-broker-jmx : MBean reference behind the JMX exporter rules
patterns/cfk-observability-baseline → concepts/observability-metrics-mapping : cross-provider query syntax once Prometheus is producing metrics
patterns/cfk-observability-baseline → concepts/schema-registry-observability : SR JMX MBeans the baseline scrapes
patterns/cfk-observability-baseline → patterns/flink-runtime-models : CMF on CFK rides this same Prometheus pipeline
patterns/cfk-observability-baseline → patterns/audit-log-siem-integration : Splunk routing complement to the metrics pipeline
patterns/cfk-observability-baseline → concepts/sla-tiers : tier-aware Grafana alert thresholds

# Inbound (existing wiki → cfk-observability-baseline)
patterns/aks-kafka-tuning → patterns/cfk-observability-baseline : Azure-specific instance of the CFK Prometheus pattern
concepts/confluent-platform-broker-jmx → patterns/cfk-observability-baseline : K8s deployment instance of broker JMX monitoring
concepts/observability-metrics-mapping → patterns/cfk-observability-baseline : implementation pattern for the self-managed K8s column
concepts/schema-registry-observability → patterns/cfk-observability-baseline : CFK deployment for SR observability

## schema-registry-observability concept (2026-05-20)

# Outbound (concept article → wiki articles it depends on)
concepts/schema-registry-observability → concepts/schema-registry-best-practices : operational surface the alerts govern
concepts/schema-registry-observability → concepts/schema-evolution-strategies : compatibility-check failure-mode signal source
concepts/schema-registry-observability → concepts/observability-metrics-mapping : cross-provider query syntax for SR metrics
concepts/schema-registry-observability → patterns/fsi-governance-automation : Terraform module enforces Compatibility per tier
concepts/schema-registry-observability → concepts/fsi-compliance : SR observability requirements for FSI audit reporting
concepts/schema-registry-observability → patterns/audit-log-siem-integration : CC compatibility-failure signal lives in audit log

# Inbound (existing wiki → SR observability)
concepts/schema-registry-best-practices → concepts/schema-registry-observability : observability surface for the operational practices
concepts/schema-evolution-strategies → concepts/schema-registry-observability : monitoring counterpart for compatibility policy
concepts/observability-metrics-mapping → concepts/schema-registry-observability : SR JMX reference for the self-managed column
patterns/fsi-governance-automation → concepts/schema-registry-observability : observability for the governance-as-code SR settings

## confluent-platform-broker-jmx concept (2026-05-20)

# Outbound (concept article → wiki articles it depends on)
concepts/confluent-platform-broker-jmx → concepts/observability-metrics-mapping : cross-provider spine that consumes these JMX MBeans
concepts/confluent-platform-broker-jmx → concepts/sla-tiers : alert thresholds per FSI tier
concepts/confluent-platform-broker-jmx → concepts/consumer-lag-monitoring : client-side lag deep dive (FetcherLag is the broker-side equivalent)
concepts/confluent-platform-broker-jmx → patterns/aks-kafka-tuning : Azure-specific tuning with JMX exporter overlap
concepts/confluent-platform-broker-jmx → patterns/dr-cluster-linking : DR-side MBean considerations

# Inbound (existing wiki → broker-jmx) — backfill ≥1 inbound
concepts/observability-metrics-mapping → concepts/confluent-platform-broker-jmx : JMX MBean reference for the self-managed column
concepts/consumer-lag-monitoring → concepts/confluent-platform-broker-jmx : broker-side FetcherLagMetrics complement to client-side lag
patterns/aks-kafka-tuning → concepts/confluent-platform-broker-jmx : JMX exporter rule reference for the broker tuning pattern

## observability-metrics-mapping concept (2026-05-20) — spine for observability expansion

# Outbound (spine → wiki articles it depends on)
concepts/observability-metrics-mapping → concepts/fsi-data-streaming-platform : provides observability templates context across six deployment models
concepts/observability-metrics-mapping → concepts/sla-tiers : alert thresholds map to FSI SLA tiers
concepts/observability-metrics-mapping → concepts/consumer-lag-monitoring : provider-specific lag deep dive
concepts/observability-metrics-mapping → patterns/audit-log-siem-integration : security-side observability complement
concepts/observability-metrics-mapping → patterns/dr-cluster-linking : consumes CL mirror lag metrics from this spine

# Inbound (existing wiki → spine) — backfill so the spine has ≥1 inbound
concepts/fsi-data-streaming-platform → concepts/observability-metrics-mapping : cross-provider mapping spine (canonical reference for the observability templates)
concepts/consumer-lag-monitoring → concepts/observability-metrics-mapping : cross-provider lag query reference
patterns/audit-log-siem-integration → concepts/observability-metrics-mapping : operational metrics spine paired with the audit-log security surface
patterns/dr-cluster-linking → concepts/observability-metrics-mapping : mirror lag metric reference for DR dashboards

## flink-event-routing pattern (2026-05-18)

# Outbound (pattern article → wiki articles it depends on)
patterns/flink-event-routing → patterns/flink-runtime-models : runtime context, state-TTL gotcha, watermark idleness
patterns/flink-event-routing → concepts/flink-confluent-cloud-setup : CC compute pools, statement lifecycle, autopilot
patterns/flink-event-routing → patterns/cdc-to-tableflow-flink-decode : specific CDC instance of the routing pattern
patterns/flink-event-routing → patterns/connect-deployment-models : where SMT routing lives in the alternative (anti-pattern) architecture
patterns/flink-event-routing → patterns/topic-naming : raw vs derived topic naming convention
patterns/flink-event-routing → concepts/schema-registry-best-practices : CI-time registration, CSFLE, derived-topic compatibility
patterns/flink-event-routing → concepts/schema-evolution-strategies : derived-topic compatibility selection
patterns/flink-event-routing → concepts/exactly-once-semantics : EOS across the producer → Flink → consumer chain
patterns/flink-event-routing → concepts/flink-checkpointing : two-phase commit for the hop

# Inbound (existing wiki → new pattern) — backfill to satisfy ≥1 inbound graph rule
patterns/flink-runtime-models → patterns/flink-event-routing : routing pattern that runs stateless on every runtime
patterns/cdc-to-tableflow-flink-decode → patterns/flink-event-routing : framework-level pattern this CDC decode specializes
patterns/connect-deployment-models → patterns/flink-event-routing : routing belongs in Flink, not in Connect SMTs

## Phase 12 — LinuxONE Accelerator ingest (2026-05-23)

# Outbound — patterns/linuxone-on-cfk-reference-architecture
patterns/linuxone-on-cfk-reference-architecture → concepts/fsi-data-streaming-platform : platform context the accelerator targets
patterns/linuxone-on-cfk-reference-architecture → concepts/linuxone-kafka-integration : LinuxONE Kafka offload context
patterns/linuxone-on-cfk-reference-architecture → concepts/linuxone-platform-foundations : s390x platform foundations
patterns/linuxone-on-cfk-reference-architecture → patterns/auditor-readonly-rbac-payload-isolation : layer 01 canonical RBAC pattern
patterns/linuxone-on-cfk-reference-architecture → patterns/flink-on-cfk-fsi-example-jobs : layer 05 canonical Flink pattern
patterns/linuxone-on-cfk-reference-architecture → concepts/fips-at-install-ocp-requirement : layer 02 OCP install dependency
patterns/linuxone-on-cfk-reference-architecture → concepts/s390x-custom-image-build-pipeline : layer 04 / layer 05 image build pipeline
patterns/linuxone-on-cfk-reference-architecture → synthesis/adr-index : ADR-009 LinuxONE deployment guidance

# Outbound — patterns/x86-to-linuxone-cluster-linking-migration
patterns/x86-to-linuxone-cluster-linking-migration → concepts/cluster-linking-topology : CL mechanism underlying the migration
patterns/x86-to-linuxone-cluster-linking-migration → patterns/dr-cluster-linking : DR pattern using same CL primitive
patterns/x86-to-linuxone-cluster-linking-migration → patterns/dr-mirrormaker2 : alternative replication backend (ADR-005 prefers CL)
patterns/x86-to-linuxone-cluster-linking-migration → patterns/linuxone-on-cfk-reference-architecture : destination architecture
patterns/x86-to-linuxone-cluster-linking-migration → synthesis/adr-index : ADR-005 CL-over-MRC decision

# Outbound — concepts/fips-at-install-ocp-requirement
concepts/fips-at-install-ocp-requirement → patterns/linuxone-on-cfk-reference-architecture : layer 02 TLS+FIPS context
concepts/fips-at-install-ocp-requirement → concepts/fsi-compliance : PCI-DSS / FFIEC encryption-in-transit context
concepts/fips-at-install-ocp-requirement → patterns/auditor-readonly-rbac-payload-isolation : layer 01 RBAC pattern that mTLS principals into

# Outbound — patterns/auditor-readonly-rbac-payload-isolation
patterns/auditor-readonly-rbac-payload-isolation → patterns/fsi-canon-overlay-for-confluent-skills : FSI RBAC overlay on upstream skills
patterns/auditor-readonly-rbac-payload-isolation → concepts/fsi-compliance : SOX/FFIEC/PCI-DSS least-privilege
patterns/auditor-readonly-rbac-payload-isolation → patterns/linuxone-on-cfk-reference-architecture : layer 01 RBAC source
patterns/auditor-readonly-rbac-payload-isolation → patterns/topic-naming : PREFIXED bindings × domain naming convention

# Outbound — concepts/s390x-custom-image-build-pipeline
concepts/s390x-custom-image-build-pipeline → concepts/linuxone-kafka-integration : LinuxONE Kafka context
concepts/s390x-custom-image-build-pipeline → concepts/linuxone-platform-foundations : s390x platform foundations
concepts/s390x-custom-image-build-pipeline → patterns/linuxone-on-cfk-reference-architecture : layer 04 Connect + layer 05 SQL-runner image consumers
concepts/s390x-custom-image-build-pipeline → patterns/flink-on-cfk-fsi-example-jobs : layer 05 SQL-runner image consumer

# Outbound — patterns/flink-on-cfk-fsi-example-jobs
patterns/flink-on-cfk-fsi-example-jobs → patterns/flink-runtime-models : CMF is one of three Flink runtime options
patterns/flink-on-cfk-fsi-example-jobs → concepts/flink-checkpointing : checkpoint encryption context (G-13)
patterns/flink-on-cfk-fsi-example-jobs → concepts/linuxone-platform-foundations : s390x foundations
patterns/flink-on-cfk-fsi-example-jobs → patterns/linuxone-on-cfk-reference-architecture : layer 05 in the 5-layer composition
patterns/flink-on-cfk-fsi-example-jobs → concepts/s390x-custom-image-build-pipeline : SQL-runner image build dependency
patterns/flink-on-cfk-fsi-example-jobs → patterns/auditor-readonly-rbac-payload-isolation : audit-trail consumer of Flink access events

# Inbound (existing wiki → new Phase 12 articles) — ≥1 inbound per H.1 STATE rule
concepts/fsi-data-streaming-platform → patterns/linuxone-on-cfk-reference-architecture : LinuxONE deployment model
concepts/linuxone-kafka-integration → patterns/linuxone-on-cfk-reference-architecture : CFK-on-OCP-on-LinuxONE pattern instance
concepts/linuxone-platform-foundations → concepts/s390x-custom-image-build-pipeline : image build for s390x compute
patterns/dr-cluster-linking → patterns/x86-to-linuxone-cluster-linking-migration : migration variant of CL
patterns/fsi-canon-overlay-for-confluent-skills → patterns/auditor-readonly-rbac-payload-isolation : RBAC payload-isolation rule
patterns/flink-runtime-models → patterns/flink-on-cfk-fsi-example-jobs : CMF FSI examples
patterns/linuxone-on-cfk-reference-architecture → concepts/fips-at-install-ocp-requirement : layer 02 inbound (parent → trip-wire concept)
concepts/cluster-linking-topology → patterns/x86-to-linuxone-cluster-linking-migration : migration use case of CL topology
concepts/fsi-compliance → patterns/auditor-readonly-rbac-payload-isolation : canonical FSI RBAC payload-isolation pattern

# Outbound — patterns/cp-mtls-self-signed-setup
patterns/cp-mtls-self-signed-setup → concepts/linuxone-jdk-tls-gotchas : IBM Semeru / FIPS / PKCS12 footguns
patterns/cp-mtls-self-signed-setup → patterns/cp-tls-debugging-by-component : per-component handshake debug recipes
patterns/cp-mtls-self-signed-setup → concepts/fips-at-install-ocp-requirement : CFK fips.enabled is no-op on non-FIPS OCP
patterns/cp-mtls-self-signed-setup → concepts/linuxone-kafka-integration : LinuxONE Kafka context
patterns/cp-mtls-self-signed-setup → patterns/auditor-readonly-rbac-payload-isolation : ACL design once mTLS is up

# Outbound — patterns/cp-tls-debugging-by-component
patterns/cp-tls-debugging-by-component → patterns/cp-mtls-self-signed-setup : the setup procedure this pattern debugs against
patterns/cp-tls-debugging-by-component → concepts/linuxone-jdk-tls-gotchas : IBM Semeru / FIPS / s390x specific failure modes
patterns/cp-tls-debugging-by-component → concepts/schema-registry-best-practices : production SR posture beyond TLS
patterns/cp-tls-debugging-by-component → patterns/connect-deployment-models : where SSL config lives across deployment models

# Outbound — concepts/linuxone-jdk-tls-gotchas
concepts/linuxone-jdk-tls-gotchas → patterns/cp-mtls-self-signed-setup : the canonical mTLS procedure this article supports
concepts/linuxone-jdk-tls-gotchas → patterns/cp-tls-debugging-by-component : handshake debug recipes per component
concepts/linuxone-jdk-tls-gotchas → concepts/fips-at-install-ocp-requirement : silent-failure trip-wire on non-FIPS OCP
concepts/linuxone-jdk-tls-gotchas → concepts/linuxone-platform-foundations : STP / UKO / CBU foundations
concepts/linuxone-jdk-tls-gotchas → concepts/linuxone-kafka-integration : z/OS bridge and platform positioning
concepts/linuxone-jdk-tls-gotchas → concepts/s390x-custom-image-build-pipeline : closing image gaps via docker buildx
concepts/linuxone-jdk-tls-gotchas → patterns/linuxone-kafka-tuning : Kafka 4.2 / CP 8.2 tuning with FSI tier overlay

# Inbound (existing wiki → new mTLS articles) — ≥1 inbound per article
concepts/fips-at-install-ocp-requirement → patterns/cp-mtls-self-signed-setup : mTLS procedure depends on FIPS-at-install for OCP-hosted CFK
concepts/linuxone-platform-foundations → concepts/linuxone-jdk-tls-gotchas : foundations referenced by the L1 gotcha catalog
patterns/auditor-readonly-rbac-payload-isolation → patterns/cp-mtls-self-signed-setup : mTLS is the auth substrate for the ACL pattern
patterns/connect-deployment-models → patterns/cp-tls-debugging-by-component : Connect deployment surfaces the SSL config landscape

# Outbound — patterns/shadowtraffic-confluent-cloud-datagen
patterns/shadowtraffic-confluent-cloud-datagen → concepts/schema-registry-best-practices : the governance/operational rules generated data must conform to
patterns/shadowtraffic-confluent-cloud-datagen → concepts/schema-aware-console-producer-required : same SR wire-format concern from the opposite direction (tools that don't speak it)
patterns/shadowtraffic-confluent-cloud-datagen → concepts/confluent-cloud-private-networking : PrivateLink reachability caveat for the generator container
patterns/shadowtraffic-confluent-cloud-datagen → patterns/topic-naming : TopicNameStrategy default that governs produce-time subject lookup regardless of schemaRegistrySubject

# Inbound — patterns/shadowtraffic-confluent-cloud-datagen
concepts/schema-registry-best-practices → patterns/shadowtraffic-confluent-cloud-datagen : data-generation pattern that must respect SR governance
concepts/schema-aware-console-producer-required → patterns/shadowtraffic-confluent-cloud-datagen : contrast case — ShadowTraffic's KafkaAvroSerializer does speak SR wire format
concepts/confluent-cloud-private-networking → patterns/shadowtraffic-confluent-cloud-datagen : PrivateLink-fronted clusters require the generator to run inside the network
patterns/topic-naming → patterns/shadowtraffic-confluent-cloud-datagen : naming-strategy background for confirming the real subject name

# patterns/schema-registry-manual-install-permissions (2026-09-09)
patterns/schema-registry-manual-install-permissions → concepts/schema-registry-best-practices : operational surface this security layer sits underneath
concepts/schema-registry-best-practices → patterns/schema-registry-manual-install-permissions : broker-side ACL/RBAC requirements for the _schemas topic
patterns/schema-registry-manual-install-permissions → patterns/yaml-topic-rbac-admin-tool : replication.factor: -1 + confluent.placement.constraints mechanism for pre-creating _schemas on MRC
patterns/yaml-topic-rbac-admin-tool → patterns/schema-registry-manual-install-permissions : ACL/RBAC requirements for the SR service principal once _schemas is pre-created
patterns/schema-registry-manual-install-permissions → concepts/kafka-streams-schema-patterns : client-side SR integration, contrasted with broker-side authorization

# patterns/kcp-msk-migration-bastion-host (2026-09-16)
patterns/kcp-msk-migration-bastion-host → patterns/dr-cluster-linking : shared mirror-topic mechanism (KCP migration-infra/migrate-topics vs. standard CC DR)
patterns/kcp-msk-migration-bastion-host → concepts/cluster-linking-topology : mirror-topic/promotion background used by the pipeline stages
patterns/kcp-msk-migration-bastion-host → concepts/confluent-cloud-private-networking : PNI gateway/ENI/wildcard-DNS mechanics behind KCP's connectivity stage
patterns/kcp-msk-migration-bastion-host → concepts/confluent-gateway : gateway-based client cutover KCP's migration flow points to
patterns/kcp-msk-migration-bastion-host → patterns/yaml-topic-rbac-admin-tool : comparable principal-to-role-binding migration tooling for CP rather than MSK→CC
patterns/dr-cluster-linking → patterns/kcp-msk-migration-bastion-host : KCP as the MSK-source path onto the same mirror-topic DR primitive
concepts/confluent-cloud-private-networking → patterns/kcp-msk-migration-bastion-host : PNI as the connectivity step in an MSK migration
concepts/confluent-gateway → patterns/kcp-msk-migration-bastion-host : gateway-based zero-config-change client switchover consumed by KCP migrations
