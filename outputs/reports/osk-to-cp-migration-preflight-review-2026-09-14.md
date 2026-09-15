# Review: OSK → CP Migration — Destination Pre-Flight Checklist + Discovery Questionnaire

**Date:** 2026-09-14
**Source files:** /Users/jhogan/Downloads/files(24)/destination-cluster-preflight-checklist.md /Users/jhogan/Downloads/files(24)/discovery-questionnaire.md
**Scope:** Cluster Linking (Apache Kafka source → Confluent Platform destination), cp-ansible on EC2, CP 8.x KRaft, listener security / ACL sync, consumer-offset sync, Schema Registry retrofit sequencing (JSON, no SR at source)
**Claims extracted:** 31 (20 preflight, 11 disco)

**Engagement context stated by the user:** no Schema Registry on the source; every payload is schema-less JSON. SR lands post-cutover and before any Flink work. Both documents already encode this correctly.

**MCP coverage note.** `confluent-docs` was the authoritative source. Five pages were fetched (Cluster Linking overview, security, configs, mirror topics, cp-ansible prerequisites, plus the CP/AK versions-interoperability matrix); each page was 130–215 KB, so I read them by targeted section (support matrix, known limitations, networking, security/ACL, Ansible enablement, offset sync, promote), not end to end. `mcp-confluent` (Cloud control plane) failed to connect this session; it is not needed for a CP-on-EC2 target. `context7` was not consulted: the one architecture claim (Cluster Linking as the migration mechanism) is covered by a `confidence: high` wiki article and the docs pages above.

---

## Summary

Both documents are directionally sound and correctly treat the missing SR as a non-blocker. Two items in the checklist and one in the questionnaire are wrong in a way that would send the client's firewall ticket to the wrong team: with an open-source Kafka source, **the link can only be destination-initiated** (source-initiated requires CP 7.8+ on the source), and **no REST Admin API is required on the source or destination** to create or manage the link. A third finding upgrades a per-app "nice to know" question into a gate: **Cluster Linking does not mirror topics that contain transactional records**, so any topic with a transactional producer needs a different migration path. Add four discovery questions (source Kafka version, message-format history, oldest client versions, transactional topics) and one checklist section (link-principal ACLs on the source), and both documents are ready to ship.

---

## Claims (YAML intermediate)

```yaml
claims:
  - id: "preflight-1"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "Confirmed scope before you start"
    category: architecture_choice
    text: "Schema Linking does not apply; SR's absence blocks no wave; the runbook's SR migration phase is not a gating step"
  - id: "preflight-2"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "Confirmed scope before you start"
    category: architecture_choice
    text: "SR lands between cutover and Flink kickoff; formalizing existing JSON topics under SR is a retrofit needing a compatibility-mode / schema-ownership design"
  - id: "preflight-3"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "1. EC2 infrastructure"
    category: config_value
    text: "EBS type/size for broker log dirs must be throughput-optimized with IOPS headroom against peak producer throughput"
  - id: "preflight-4"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "1. EC2 infrastructure"
    category: config_value
    text: "Brokers spread across AZs with broker.rack matching AZ placement"
  - id: "preflight-5"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "2. Ansible readiness"
    category: config_value
    text: "Python version on target hosts matches cp-ansible's supported version"
  - id: "preflight-6"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "2. Ansible readiness"
    category: config_value
    text: "cp-ansible version pinned and matches the target CP version exactly"
  - id: "preflight-7"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "2. Ansible readiness"
    category: config_value
    text: "Inventory reflects real hostnames/IPs, broker IDs, and rack/AZ assignments"
  - id: "preflight-8"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "3. Security configuration"
    category: config_value
    text: "Security protocol from Discovery P2 translated into listener config matching what OSS apps need"
  - id: "preflight-9"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "3. Security configuration"
    category: architecture_choice
    text: "RBAC or ACL authorization model configured to match Discovery P5, not defaulted to open authz"
  - id: "preflight-10"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "4. Networking / connectivity for Cluster Linking"
    category: architecture_choice
    text: "Link direction (source- vs destination-initiated) decided per Discovery P4, with the corresponding firewall rule requested"
  - id: "preflight-11"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "4. Networking / connectivity for Cluster Linking"
    category: behavior_assertion
    text: "Connectivity test completed in both directions relevant to the chosen link direction"
  - id: "preflight-12"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "4. Networking / connectivity for Cluster Linking"
    category: behavior_assertion
    text: "Admin REST API enabled and reachable on both source and destination clusters — required to create/manage the link"
  - id: "preflight-13"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "4. Networking / connectivity for Cluster Linking"
    category: behavior_assertion
    text: "DNS or stable IPs confirmed for both clusters so the link config need not be rebuilt on address change"
  - id: "preflight-14"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "5. Cluster-level configuration"
    category: config_value
    text: "Replication factor and min.insync.replicas set deliberately, not left at broker defaults"
  - id: "preflight-15"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "5. Cluster-level configuration"
    category: config_value
    text: "Topic auto-creation disabled on the target"
  - id: "preflight-16"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "5. Cluster-level configuration"
    category: config_value
    text: "Retention and cleanup policy defaults reviewed; don't assume OSS defaults apply"
  - id: "preflight-17"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "5. Cluster-level configuration"
    category: config_value
    text: "Broker-level quotas considered if the cluster carries mirrored and pilot traffic simultaneously"
  - id: "preflight-18"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "6. Monitoring & validation"
    category: metric_sla
    text: "Per-topic lag monitoring available (not just link-level aggregate) ahead of Phase 5"
  - id: "preflight-19"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "7. Smoke test"
    category: behavior_assertion
    text: "Simulate broker failure/restart; confirm ISR recovers and no data loss on the test topic"
  - id: "preflight-20"
    source_file: "destination-cluster-preflight-checklist.md"
    source_section: "Explicitly out of scope"
    category: architecture_choice
    text: "Schema Registry not required for cutover because source is all JSON; Flink sequenced after SR"
  - id: "disco-1"
    source_file: "discovery-questionnaire.md"
    source_section: "P1. Bootstrap servers"
    category: behavior_assertion
    text: "Whether bootstrap.servers is a platform-controlled VIP/DNS name or a raw broker list determines cutover mechanics"
  - id: "disco-2"
    source_file: "discovery-questionnaire.md"
    source_section: "P2. Security protocol"
    category: config_value
    text: "Current security protocol is one of PLAINTEXT, SASL_PLAINTEXT, SASL_SSL, or mTLS; may vary by team; some apps may be on no-auth"
  - id: "disco-3"
    source_file: "discovery-questionnaire.md"
    source_section: "P3. Schema Registry — CONFIRMED"
    category: architecture_choice
    text: "No SR on source, all JSON; SR is post-cutover, pre-Flink; not a cutover dependency"
  - id: "disco-4"
    source_file: "discovery-questionnaire.md"
    source_section: "P4. Network reachability & link direction"
    category: architecture_choice
    text: "Whichever side can open inbound more easily decides source-initiated vs destination-initiated"
  - id: "disco-5"
    source_file: "discovery-questionnaire.md"
    source_section: "P5. Authorization model"
    category: architecture_choice
    text: "Authorization is via native Kafka ACLs or external enforcement (proxy, sidecar, app layer)"
  - id: "disco-6"
    source_file: "discovery-questionnaire.md"
    source_section: "P6. Producer pause tolerance"
    category: behavior_assertion
    text: "Cutover requires a brief producer write pause; some tiers may have zero tolerance"
  - id: "disco-7"
    source_file: "discovery-questionnaire.md"
    source_section: "PLATFORM-LEVEL — ACLs"
    category: architecture_choice
    text: "External authz enforcement needs its own migration plan; out of scope for Cluster/Schema Linking"
  - id: "disco-8"
    source_file: "discovery-questionnaire.md"
    source_section: "PER-APPLICATION — Groups / offsets"
    category: behavior_assertion
    text: "Exact group.id (static vs dynamically generated) and any planned renames matter for migration"
  - id: "disco-9"
    source_file: "discovery-questionnaire.md"
    source_section: "PER-APPLICATION — Producer tolerance"
    category: behavior_assertion
    text: "Whether the app uses transactional/idempotent producers on the topic is relevant to cutover tolerance"
  - id: "disco-10"
    source_file: "discovery-questionnaire.md"
    source_section: "PLATFORM-LEVEL — Schema Registry"
    category: architecture_choice
    text: "SR discovery is N/A now; revisit as a separate pass when the post-cutover SR workstream starts"
  - id: "disco-11"
    source_file: "discovery-questionnaire.md"
    source_section: "PER-APPLICATION — Auth"
    category: config_value
    text: "Client library and version are collected per app"
```

---

## Claim Validation

### destination-cluster-preflight-checklist.md — Confirmed scope / out of scope

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| preflight-1 | Schema Linking N/A; SR absence gates nothing | `concepts/cluster-linking-topology.md` (Schema Linking is separate); `patterns/x86-to-linuxone-cluster-linking-migration.md` §2.4 trip-wire | confluent-docs CL overview (CL replicates topic data/metadata only) | — | — | Confirmed |
| preflight-2 | SR post-cutover, pre-Flink; JSON→SR is a retrofit needing compat-mode/ownership design | `patterns/schema-registry-adoption-playbook.md` (Category B: JSON, no SR → producers first); `concepts/schema-registry-best-practices.md` | — | kafka-schema-registry | Confirmed | Confirmed |
| preflight-20 | SR not required for cutover; Flink after SR | same as preflight-1/2 | same | — | — | Confirmed |

**Corrections:** none. **Canon notes on preflight-2:** when the SR workstream opens, canon default is Avro or Protobuf in production, with JSON Schema reserved for the gradual-migration bridge (wiki playbook: "JSON Schema for gradual migrations from plain JSON"). Rollout order for Category B is producers first with the Confluent serializer, then consumers with the Confluent deserializer; consumers reading raw JSON keep working during the producer phase only if the schema-ID header location is used. Compatibility mode: `BACKWARD` base default, tier-derived under the FSI overlay (ADR-002), `FULL_TRANSITIVE` for critical-tier subjects.

### destination-cluster-preflight-checklist.md — §1 EC2 / §2 Ansible

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| preflight-3 | EBS throughput-optimized, IOPS headroom | — | not fetched (CP system-requirements page) | — | — | Unverifiable |
| preflight-4 | `broker.rack` = AZ | — | stable Kafka behavior; not re-fetched | — | — | Confirmed |
| preflight-5 | Python on targets matches cp-ansible support | — | confluent-docs cp-ansible prerequisites | — | — | Confirmed |
| preflight-6 | cp-ansible pinned 1:1 with CP version | — | confluent-docs cp-ansible prerequisites ("highly recommended" 1:1 table) | — | — | Confirmed |
| preflight-7 | Inventory: hostnames, broker IDs, rack/AZ | — | confluent-docs CL overview (KRaft/ZK section); versions-interoperability | — | — | Corrected |

**Corrections:**
- **preflight-7 (incomplete, Corrected):** CP 8.0+ is KRaft-only ("ZooKeeper is no longer available for new deployments as of Confluent Platform 8.0"). The inventory checklist item must include the `kraft_controller` host group and controller placement across AZs, not only broker IDs. Add: controller quorum size (3 or 5), controllers on separate hosts from brokers for prod, and `password.encoder.secret` is *not* required in KRaft mode for Cluster Linking (it was on ZK).
- **preflight-5 (sharpen):** for CP 8.x, cp-ansible requires Ansible 9.x–11.x with Python 3.10–3.12 on *both* control and target nodes, set as system default. RHEL 8 targets work only with Ansible 9.x. Also required and missing from the checklist: `sudo` for the SSH user, `en_US.UTF-8` locale, NTP/chrony time sync on every broker, IPv6 JVM flag `-Djava.net.preferIPv6Addresses=true` on `kafka_broker` if the cluster is IPv6.
- **preflight-3 (Unverifiable):** not checked against the CP system-requirements page. Field default is gp3 with provisioned throughput/IOPS or io2 for tier-1; verify before quoting.

### destination-cluster-preflight-checklist.md — §3 Security

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| preflight-8 | Listener config matches Discovery P2 | `patterns/cp-mtls-self-signed-setup.md` | confluent-docs CL overview, known limitations | — | — | Confirmed |
| preflight-9 | RBAC/ACL model matches P5, not open authz | `patterns/auditor-readonly-rbac-payload-isolation.md`; canon `auth_mechanism: mTLS + RBAC` | confluent-docs CL security (ACL sync prerequisites) | — | — | Confirmed |

**Corrections / additions:**
- **preflight-8:** docs add a hard rule the checklist should carry verbatim: "Do not use unauthenticated listeners with Confluent Platform. Cluster Linking can access the listeners, increasing the security risk." If any OSS apps are on PLAINTEXT (Discovery P2), the CP side must still not expose a PLAINTEXT listener; those apps get credentials as part of cutover.
- **preflight-8:** keystores/truststores/keytabs used by the link must be at the *same path on every destination broker* and must not live under `/tmp`, or the link fails on some brokers.
- **preflight-9:** the checklist has no item for the **link principal's ACLs on the source cluster** (Describe/Read on the mirrored topics, Describe on cluster; Describe on consumer groups if offset sync is on; the source needs an authorizer, `AclAuthorizer` on OSS is fine). Add it. Also: `acl.sync.enable` cannot be combined with `cluster.link.prefix`.

### destination-cluster-preflight-checklist.md — §4 Networking / Cluster Linking

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| preflight-10 | Link direction decided per P4 | `concepts/cluster-linking-topology.md` (source-initiated: CP 7.1+) | confluent-docs CL overview support matrix | — | — | **Corrected** |
| preflight-11 | Connectivity tested in both directions | same | confluent-docs CL overview (networking requirements; promote reachability) | — | — | **Corrected** |
| preflight-12 | Admin REST API on both clusters required for link mgmt | `concepts/cluster-linking-topology.md` (CP management via `kafka-cluster-links` / `kafka-mirrors`) | confluent-docs CL overview + configs | — | — | **Corrected** |
| preflight-13 | Stable DNS/IPs for both clusters | `patterns/dr-application-routing.md` (advertised listeners must be logical FQDNs) | — | — | — | Confirmed |

**Corrections:**
- **preflight-10 (Corrected, Critical):** The supported-combinations table lists source-initiated links only for "Confluent Platform 7.8.0 or later (source-initiated link)" sources. Apache Kafka appears only as a destination-initiated source ("Kafka 3.8.x or later → Confluent Platform 7.8.0 or later"). **With an OSS source there is no direction decision to make: the link is destination-initiated, full stop.** The firewall rule is one-way: CP broker hosts → every OSS broker on its advertised listener port, and the TCP connection must be allowed to persist (docs: "Firewalls ... must allow the TCP connection to persist"). If the client's OSS side cannot accept inbound from CP, that is a Cluster Linking blocker, not a direction choice; the fallbacks are MirrorMaker 2 or Replicator.
- **preflight-11 (Corrected):** only one direction needs testing: destination brokers → source brokers. Test from *each* CP broker host, not from a bastion, because every destination broker that leads a mirror partition fetches directly. The same reachability is required again at `promote` time: "The destination cluster's brokers must be able to reach the source cluster's brokers to make this check, so your source cluster must be online."
- **preflight-12 (Corrected):** No REST API is required on either side. Links are created and managed from the destination with `kafka-cluster-links` / `kafka-mirrors` (Kafka protocol) or the Confluent CLI; the Confluent REST Admin API v3 on the *destination* is optional and matters only for (a) REST-based automation and (b) Control Center rendering mirror topics correctly. An OSS source has no Confluent REST API and needs none. Rewrite the item as: "Confluent CLI or `kafka-cluster-links` reachable to the destination bootstrap from the operator host; REST v3 on destination only if C3 or REST automation is in scope."
- **preflight-13 (add):** the link stores the source `bootstrap.servers`; the source's `advertised.listeners` must also be stable and resolvable from the CP hosts, since fetchers follow metadata, not bootstrap.

### destination-cluster-preflight-checklist.md — §5 Cluster config / §6 Monitoring / §7 Smoke test

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| preflight-14 | RF / `min.insync.replicas` set deliberately | canon `replication_factor: 3`, `min_insync_replicas: 2` | — | — | — | Confirmed |
| preflight-15 | Topic auto-creation disabled | canon `auto_create_mirror_topics: false` | confluent-docs mirror topics (auto-create filters) | — | — | Confirmed |
| preflight-16 | Retention/cleanup defaults reviewed | — | confluent-docs mirror topics (`topic.config.sync`) | — | — | Confirmed |
| preflight-17 | Quotas if mirrored + pilot traffic coexist | — | confluent-docs CL overview (CL writes throttled first on destination) | — | — | Confirmed |
| preflight-18 | Per-topic lag monitoring before Phase 5 | `patterns/cluster-linking-observability.md` (CP JMX `MirrorLag` per partition, per-tier thresholds) | — | — | — | Confirmed |
| preflight-19 | Broker-failure smoke test, ISR recovery | — | stable Kafka behavior | — | — | Confirmed |

**Corrections / additions:**
- **preflight-15:** disable both `auto.create.topics.enable` on the brokers *and* keep `auto.create.mirror.topics.enable=false` on the link (canon). If auto-mirror is later turned on for convenience, it silently excludes `_confluent*` topics and cannot be chained with a prefix.
- **preflight-16:** mirror topics inherit source topic configs via `topic.config.sync` (retention, cleanup policy, etc.); destination broker defaults apply only to non-mirrored topics. Review the source's per-topic configs, not just the destination defaults. Partition counts are copied exactly and cannot be changed while mirrored.
- **preflight-17:** confirmed and sharpened: on the destination, Cluster Linking writes have lower priority than client produce traffic and are throttled first, so pilot producers on the same cluster will starve the mirror before they feel it themselves. Watch mirror lag, not just broker CPU.
- **§5 (add):** `offsets.retention.minutes` on the destination must be at least double `offsets.retention.check.interval.ms` above the source, or synced consumer offsets deleted on the source persist on the destination and re-replicate.
- **§7 (add):** run a throwaway link end-to-end in non-prod (create link → mirror one topic → sync one group → `promote`) before the prod build is declared launch-ready. A cluster that forms cleanly is not evidence the link works.

### discovery-questionnaire.md — Priority questions

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| disco-1 | VIP/DNS vs raw broker list drives cutover | `patterns/dr-application-routing.md` | — | — | — | Confirmed |
| disco-2 | Protocol is PLAINTEXT / SASL_PLAINTEXT / SASL_SSL / mTLS | canon: never username/password in FSI | confluent-docs CL security (link is a client of the source: any SASL mechanism or mTLS) | — | — | Confirmed |
| disco-3 | No SR; post-cutover, pre-Flink | as preflight-1/2 | as preflight-1/2 | kafka-schema-registry | Confirmed | Confirmed |
| disco-4 | Easier inbound side decides link direction | `concepts/cluster-linking-topology.md` | confluent-docs CL overview support matrix | — | — | **Corrected** |
| disco-5 | Native ACLs vs external enforcement | — | confluent-docs CL security (ACL sync needs an authorizer; `AclAuthorizer` supported) | — | — | Confirmed |
| disco-6 | Cutover needs a producer pause; some tiers can't | `patterns/x86-to-linuxone-cluster-linking-migration.md` §2.5 (stop producers → lag 0 → promote) | confluent-docs mirror topics (`promote` checks zero mirroring/config/offset lag) | — | — | Confirmed |

**Corrections:**
- **disco-4 (Corrected, Critical):** same finding as preflight-10. Replace P4 with: "Can every OSS broker accept a persistent inbound TCP connection from the CP broker subnet on the advertised listener port? (Cluster Linking from open-source Kafka is destination-initiated only.) If not, what is the lead time on that rule, and is MM2/Replicator the fallback?" The "whose ticket gets filed first" framing is still useful; the answer is just always the OSS side's ticket.
- **disco-2 (add):** the link authenticates to the source as an ordinary Kafka client, so the source needs a service principal for the link with whatever mechanism the OSS cluster runs. If the OSS cluster is PLAINTEXT, the link works technically, but CP docs prohibit unauthenticated listeners on the CP side, and canon prohibits it outright in FSI. Ask on the call: "Can a new SASL/SCRAM or mTLS principal be issued on the OSS cluster for the link before cutover?"
- **disco-6 (FSI overlay):** frame the pause per SLA tier. Sub-millisecond (market data) and <10 ms (risk) tiers cannot absorb even a short pause; those producers need a dual-write or drain-then-switch plan rather than "pause and promote." Compliance (<100 ms) and reconciliation (async) tiers tolerate the promote window.

### discovery-questionnaire.md — Platform-level and per-application

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| disco-7 | External authz out of scope for Cluster/Schema Linking | — | confluent-docs CL security (only ACLs sync; proxy auth unsupported) | — | — | Confirmed |
| disco-8 | Exact `group.id`, static vs dynamic, renames | — | confluent-docs mirror topics (offset sync filters by group name/pattern; `consumer.group.prefix.enable`) | — | — | Confirmed |
| disco-9 | Transactional/idempotent producer relevant to cutover tolerance | `concepts/cluster-linking-topology.md` says transactional records replicate without cross-topic atomicity | confluent-docs CL overview known limitations; mirror topics (`__transaction_state` not replicated) | — | — | **Corrected** |
| disco-10 | SR discovery deferred to the SR workstream | as preflight-2 | — | kafka-schema-registry | Confirmed | Confirmed |
| disco-11 | Client library and version collected | — | versions-interoperability (CP 8.0 / Kafka 4.0 dropped older client protocol versions) | — | — | Confirmed |

**Corrections:**
- **disco-9 (Corrected, Critical):** this is a gate, not a tolerance question. Docs, known limitations: "Cluster Linking doesn't support mirroring topics that contain messages produced using the Kafka transactions feature," and `__transaction_state` is explicitly not replicated "because Cluster Linking does not support transactions." Idempotent (non-transactional) producers are fine. Any topic with a transactional producer (Kafka Streams EOS apps, `transactional.id` set) needs a different path: drain-and-recreate at cutover, or MM2/Replicator for those topics. Reword: "Does any producer on this topic set `transactional.id` (including Kafka Streams with `processing.guarantee=exactly_once_v2`)? If yes, this topic cannot be migrated by Cluster Linking." ⚠️ Wiki (`cluster-linking-topology.md` Limitations) says transactional messages *are* replicated without cross-topic atomicity; MCP is authoritative and stricter. Flag for `/wiki:validate`.
- **disco-11 (add):** CP 8.x is Kafka 4.x; Kafka 4.0 removed support for very old client protocol versions (versions-interoperability, "Starting with Confluent Platform 8.0 (based on Kafka 4.0), support for older client protocols..."). Add: "What is the *oldest* client library version in your portfolio?" Anything pre-2.1-era Java or a very old librdkafka will not connect to CP 8.x at all and must be upgraded before cutover, not after.
- **disco-8 (add):** offset sync is off by default (`consumer.offset.sync.enable=false`) and is filtered by group name. Dynamically generated `group.id`s cannot be listed in the filter; those apps either use a pattern filter or accept a fresh start at `auto.offset.reset`. Also ask: "Will the same `group.id` ever be active on both clusters during the pilot?" (docs: disable offset sync until you have verified which groups exist on the destination).

---

## Premise Challenge

| # | Premise | Assumption | Challenge | Severity |
|---|---------|------------|-----------|----------|
| 1 | Cluster Linking is viable from this OSS source | Source runs a supported Kafka version, every topic holds v2+ record batches, no transactional topics, CP brokers can reach OSS brokers | Neither doc asks the source Kafka version. The support table lists "Kafka 3.8.x or later" as the OSS source row, with a footnote pointing to the CP/AK compatibility page; older OSS versions are at best unverified. Topics on a cluster upgraded from pre-0.11 with an old `log.message.format.version` can contain v0/v1 batches, which move the mirror to `FAILED`. Transactional topics are unsupported outright. Any one of these turns the migration into MM2/Replicator for some or all topics. | Critical |
| 2 | Link direction is a free choice driven by firewall convenience | Both clusters support both initiation modes | Source-initiated needs CP 7.8+ on the source. OSS source ⇒ destination-initiated only. | Critical |
| 3 | "No SR" means nothing schema-related touches cutover | Consumers deserialize JSON by convention and will keep doing so on CP | True for the link itself. But the SR retrofit is Category B (producers first, then consumers); if any consumer team upgrades to a Confluent deserializer before its producers switch, it breaks on raw JSON. Sequence the retrofit per topic, not per team. Flink on CP (CMF) can read schema-less JSON with an explicit DDL, so "SR before Flink" is a governance choice, not a technical prerequisite; keep it, but say why. | Moderate |
| 4 | Consumer groups carry over with their offsets | Offset sync is enabled and filtered correctly | Off by default; requires group-name filters; dynamic `group.id`s cannot be enumerated; `offsets.retention.minutes` mismatch causes re-replication of deleted offsets. | Moderate |
| 5 | The authz model ports across | Source uses native ACLs with an authorizer | Only native ACLs sync (source must run `AclAuthorizer` or equivalent). External/proxy enforcement does not, and CL cannot authenticate through a proxy. If the target uses RBAC (canon for FSI), synced ACLs land alongside RBAC bindings; someone must own the mapping. | Moderate |
| 6 | A brief producer pause is acceptable portfolio-wide | No sub-millisecond / <10 ms tier producers | P6 asks the right question; the FSI SLA tiers give the answer shape: market-data and risk tiers need dual-write or drain-and-switch, not pause-and-promote. | Minor |

---

## Canon Compliance

| Area | Status | Notes |
|------|--------|-------|
| Cluster/topic design (RF 3, `min.insync.replicas` 2) | Compliant | Checklist §5 asks for deliberate values; canon supplies them. Mirror topics take partition count from source. |
| Topic auto-creation / `auto.create.mirror.topics.enable=false` | Compliant | Checklist disables broker auto-create; add the link-level flag explicitly. |
| Cluster Linking over MM2 for migration | Compliant, conditional | Correct choice for OSS→CP *if* premise 1 holds. Document the MM2/Replicator fallback for transactional or v0/v1 topics. |
| Security (mTLS + RBAC, no username/password in FSI, no unauthenticated listeners) | Partially compliant | Checklist allows "if SASL" without excluding PLAIN. In FSI context, SASL/PLAIN is out; SCRAM-SHA-512 minimum, mTLS preferred. Add the CP "no unauthenticated listeners" rule. |
| Service account per application | Not addressed | Add a link-principal item and a per-app principal item to §3. |
| Audit log on all production clusters | Not addressed | cp-ansible has an audit-logs role; add to §3 or §6. Required for the FSI evidence package (wiki migration article §4.3). |
| Schema Registry (Avro/Protobuf prod; `BACKWARD` default; tier-derived in FSI) | Deferred, correctly | Both docs defer SR. When the workstream opens, apply `patterns/schema-registry-adoption-playbook.md` Category B ordering and ADR-002 compatibility-by-tier. |
| Producer defaults (`acks=all`, idempotence) | Not addressed | Out of scope for a destination checklist; belongs in the per-app questionnaire as "what are your `acks` / `enable.idempotence` values today?" since CP 8.x defaults them on and some OSS apps may override. |
| Exactly-once / regulatory reporting (FSI overlay) | Gap | Transactional topics are a CL blocker (disco-9). Any regulatory-reporting pipeline built on EOS needs its own migration path and an evidence trail. |
| Observability (per-topic lag, thresholds by tier) | Compliant | §6 aligns with `patterns/cluster-linking-observability.md`. |

---

## Gaps

- **preflight-3** EBS sizing guidance: not verified against the CP system-requirements page this session.
- **Source Kafka minimum version for a Cluster Linking source**: the support table says "Kafka 3.8.x or later" while the footnote says CL works on "all currently supported versions of Confluent Platform and Kafka." Which governs for a 3.x source below 3.8 is not stated on the page. Treat 3.8+ as safe, below that as "ask Support."
- **Wiki drift**: `concepts/cluster-linking-topology.md` Limitations says transactional messages are replicated without cross-topic atomicity; confluent-docs says transactional topics are unsupported. Queue for `/wiki:validate`.
- **No wiki article** for OSS-Kafka-source Cluster Linking migration (this engagement's shape) or for cp-ansible deployment prerequisites. Both auto-stubbed in `wiki/_queue.md`.
- **Kafka 4.0 client-protocol floor**: the exact oldest supported client version was not extracted from the versions page; verify before telling app teams a number.

---

## Recommendations

**Fix in the checklist (§4):**
1. Replace the direction item with: "Link is destination-initiated (OSS source). Firewall rule: CP broker hosts → every OSS broker, advertised listener port, persistent TCP."
2. Replace the both-directions test with: "From each CP broker host, open a Kafka client connection to every OSS broker's advertised address and complete a metadata fetch with the link principal."
3. Replace the REST item with: "Confluent CLI / `kafka-cluster-links` can reach the destination bootstrap from the operator host. REST Admin v3 on destination only if Control Center or REST automation is in scope. Nothing on the source."

**Add to the checklist:**
4. §2: `kraft_controller` group in inventory; controllers on separate hosts; 3 or 5 quorum; `sudo`, locale, time sync, IPv6 JVM flag if applicable.
5. §3: link principal created on the source with Describe/Read on in-scope topics, Describe on cluster, Describe on groups; keystore/truststore at identical paths on all CP brokers, never under `/tmp`; no unauthenticated listener on CP; audit log enabled.
6. §5: `offsets.retention.minutes` rule; note that mirror topics inherit source topic configs.
7. §7: full link rehearsal in non-prod (link → mirror → offset sync → promote) as the launch-ready gate.

**Fix in the questionnaire:**
8. P4: reword to the one-way inbound question above; add the MM2/Replicator fallback branch.
9. Per-app "transactional/idempotent": split into two questions; make `transactional.id` / Kafka Streams EOS a hard flag ("cannot migrate via Cluster Linking").

**Add to the questionnaire (priority tier):**
10. "What Kafka version is the OSS cluster on, and what was it upgraded from? Has `log.message.format.version` ever been pinned below 0.11?" (v0/v1 batches fail the mirror.)
11. "Oldest client library version in the portfolio?" (Kafka 4.x protocol floor.)
12. "Can a service principal for the link be issued on the OSS cluster before cutover, using the current mechanism?"
13. P6: ask which SLA tier each zero-tolerance producer sits in; sub-ms and <10 ms tiers get a dual-write plan.

**Post-cutover SR workstream (carry forward, not now):** apply the adoption playbook's Category B ordering per topic, Avro or Protobuf as the target format with JSON Schema only as a bridge, compatibility by tier per ADR-002, and decide schema ownership before the first subject is registered.

---

Canon stack: base + industry/fsi | Hash: 437a88b8eb364e19 | MANIFEST: 1.1.0 | Floor: claude-fable-5-1 | Generated: 2026-09-14T23:48:41Z
