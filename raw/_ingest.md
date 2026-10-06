---
title: Ingest Queue
last_updated: 2026-05-20
---

# Ingest Queue

Files listed here are pending compilation into the wiki.
Run: `python tools/wiki-compile.py --delta` to process.

## Pending

<!-- format:
- path: raw/articles/my-article.md
  source_url: https://...
  added: YYYY-MM-DD
  notes: optional context for the compiler
-->


<!-- both April-17 entries processed 2026-05-18 — see Processed section below -->
<!-- oic-kafka-integration auto-stub processed 2026-05-18 — see Processed section below -->


# === Phase H.1: confluent-agent-skills@91d1871e ingest queue ===
# All 19 H.1 entries processed (10 parents in H.1-02 + 9 trip-wires in H.1-03);
# entries moved to ## Processed below. Only the 2 pre-H.1 April-2026 entries remain in Pending.

# === Observability Expansion (2026-05-20): 6 articles closing CC-vs-self-managed gap ===
# Sequenced per a local plan file.
# All 6 articles processed 2026-05-20.

## Processed

- path: raw/repos/kcp-bastion-migration-usage.md
  source_url: local kcp source clone, local kcp working directory, and internal field notes (local, not client-visible); https://docs.confluent.io/cloud/current/clusters/migrate-kcp.html (MCP-validated)
  notes: |
    Practitioner's hands-on KCP (Copy Paste) usage — not compiled from the
    marketing blog alone. Confirmed via confluent-docs MCP: official tool
    name ("Copy Paste (kcp)"), command groups, bastion-host guidance for
    private-network clusters, and gateway-based client cutover. Foregrounds
    the standalone `kcp create-asset bastion-host` quick-provisioning use
    case (the practitioner's primary use) ahead of the full multi-stage migration
    pipeline, per explicit clarification. IAM policy tiers and generated
    Terraform detail are sourced from the practitioner's own iteratively-hardened runbooks
    (not officially published by Confluent) — flagged inline as unverified
    against MCP. All real AWS account IDs/ARNs/credentials found in
    msk-credentials.yaml and terraform.tfstate were excluded/generalized.
  compiled: 2026-09-16
  wiki_articles:
    - wiki/patterns/kcp-msk-migration-bastion-host.md

- path: raw/repos/cp-migration-demo-rehearsal.md
  source_url: ~/GoodLabs/cp-migration-demo (local repo, not pushed to a remote)
  notes: |
    Hands-on rehearsal rig for the CP -> MRC live-migration pattern. Two tracks (Docker Compose + real cp-ansible),
    both run and verified end-to-end in-session, not just written.
  compiled: 2026-09-08
  wiki_articles:
    - wiki/patterns/cp-mrc-migration-rehearsal-rig.md

- path: mTLS-CP-LinuxOne.md (user-provided runbook, not vendored)
  source_url: |
    mTLS-CP-LinuxOne.md (raw user-provided runbook)
    https://docs.confluent.io/platform/current/security/protect-data/encrypt-tls.html
    https://docs.confluent.io/platform/current/security/authorization/acls/overview.html
    https://docs.confluent.io/platform/current/schema-registry/installation/config.html
    https://docs.confluent.io/control-center/current/installation/configuration.html
    https://docs.confluent.io/platform/current/connect/security.html
  added: 2026-05-27
  notes: |
    /wiki:ingest invoked with a user-provided mTLS-CP-LinuxOne.md. The runbook
    is a 628-line end-to-end Confluent Platform mTLS guide written with LinuxONE / IBM
    Semeru / FIPS context (Sections 0-9 plus Appendix A on s390x non-SSL hurdles and
    Appendix B on per-component debug recipes). Split into THREE wiki articles to keep
    each focused and individually navigable:

      1. wiki/patterns/cp-mtls-self-signed-setup.md (pattern template) — Sections 0-7
         and §9. Canonical mTLS procedure: CA gen, broker keystore + EKU=serverAuth+clientAuth,
         shared truststore, client keystore, broker server.properties with ssl.client.auth=
         required + StandardAuthorizer + ssl.principal.mapping.rules, client.properties,
         openssl/kafka-broker-api-versions/topic+produce+consume verification, kafka-acls.
         confidence: high — full MCP validation gate against confluent-docs encrypt-tls.html
         (ssl.client.auth=required vs requested discouraged; ssl.endpoint.identification.
         algorithm) and ACL overview (StandardAuthorizer at org.apache.kafka.metadata.
         authorizer.StandardAuthorizer for KRaft; super.users; allow.everyone.if.no.acl.found;
         ssl.principal.mapping.rules canonical name). Source-specific names/domains were replaced
         with placeholders (Example/example.internal).

      2. wiki/patterns/cp-tls-debugging-by-component.md (pattern template) — Appendix B.
         Per-component debug recipes (client / broker-to-broker / SR kafkastore-vs-REST /
         C3 multi-downstream / Connect 3-surface / app / tcpdump / diagnostic bundle).
         Documents the *_OPTS injection points (KAFKA_OPTS, SCHEMA_REGISTRY_OPTS,
         CONTROL_CENTER_OPTS), JVM debug flags, grep markers, and the
         ssl.client.auth (broker) vs ssl.client.authentication (SR/Connect REST) property-
         name asymmetry. confidence: high — MCP-validated against Connect security
         docs (producer.ssl.* / consumer.ssl.* / admin.ssl.* / listeners.https.* prefix
         that overrides top-level ssl.*), SR config (kafkastore.ssl.* for backing store,
         ssl.client.authentication for REST), and C3 config (confluent.controlcenter.
         streams.ssl.* / .connect.<name>.* / .ksql.* / .schema.registry.* namespaces).
         Two inline ⚠️ unverified markers retained: (a) exact SCHEMA_REGISTRY_OPTS /
         CONTROL_CENTER_OPTS env var names (operational convention, not surfaced in fetched
         docs), (b) confluent.monitoring.interceptor.* namespace (interceptor JAR pattern
         is canonical but not in the C3 config page).

      3. wiki/concepts/linuxone-jdk-tls-gotchas.md (concept template) — Section 8 + Appendix A.
         IBM Semeru / FIPS / s390x specific failure modes: IBMJCE/IBMJSSE2 provider order,
         FIPS mode and PKCS12 MAC algorithm (HmacPBESHA256 forcing flags), cipher suite
         intersection x86↔s390x, TLS 1.3 quirks on older Semeru, PKCS#11/CEX wiring
         (CCA vs EP11), time skew/STP, hostname/SAN matching. Plus non-SSL s390x hurdles:
         multi-arch image discipline (QEMU emulation footgun), RocksDB JNI for Kafka
         Streams, connector JAR JNI compatibility, endianness in custom serializers.
         confidence: medium — most claims here are IBM-JDK / FIPS / s390x territory rather
         than Confluent product surface, so confluent-docs MCP isn't the primary validator.
         Three inline ⚠️ unverified markers retained: (a) IBMJCE/IBMJSSE2 default ordering
         on Semeru, (b) exact PKCS#11+CEX wiring syntax, (c) IBM JDK TLS 1.3 quirks tied
         to specific Semeru versions. Cross-linked to fips-at-install-ocp-requirement,
         linuxone-platform-foundations, linuxone-kafka-integration, s390x-custom-image-
         build-pipeline.

    All three articles cross-link to each other and to existing LinuxONE/FSI wiki content.
    Index updated under Concepts (jdk-tls-gotchas) and Patterns (mtls-setup, tls-debugging).
    Graph backlinks added (≥1 inbound, ≥1 outbound per new article).
  compiled: 2026-05-27
  wiki_articles:
    - wiki/patterns/cp-mtls-self-signed-setup.md
    - wiki/patterns/cp-tls-debugging-by-component.md
    - wiki/concepts/linuxone-jdk-tls-gotchas.md

- path: <none — MCP-only ingest, no rich raw source>
  source_url: |
    https://docs.confluent.io/cloud/current/monitoring/metrics-api.html (10 ksqlDB metrics confirmed)
    https://docs.confluent.io/platform/current/ksqldb/operate-and-deploy/monitoring.html
    https://docs.confluent.io/platform/current/streams/monitoring.html
  added: 2026-05-20
  notes: |
    /wiki:ingest invoked with target wiki/concepts/ksqldb-observability.md (concept template).
    Article 6 (final) of the observability expansion. CC + self-managed ksqlDB observability.
    Closes the only fully-uncovered component gap from the audit (ksqlDB had zero coverage).
    MCP validation: 10 CC ksqlDB metrics MCP-confirmed (io.confluent.kafka.ksql/{committed_offset_lag,
    consumed_total_bytes, offsets_processed_total, processing_errors_total, produced_total_bytes,
    query_restarts, query_saturation, storage_utilization, streaming_unit_count, task_stored_bytes}).
    Self-managed ksqlDB-specific JMX MBean tree (io.confluent.ksql.metrics:type=*) and underlying
    Kafka Streams MBeans documented from upstream docs. One ⚠️ unverified marker on exact
    attribute names. confidence: medium.
  compiled: 2026-05-20
  wiki_articles:
    - wiki/concepts/ksqldb-observability.md

- path: raw/repos/fsi-dsp/observability/grafana/dashboard-dr-readiness.json
  source_url: |
    raw/repos/fsi-dsp/observability/grafana/dashboard-dr-readiness.json
    https://docs.confluent.io/cloud/current/multi-cloud/cluster-linking/dr-failover.html
    https://docs.confluent.io/cloud/current/multi-cloud/cluster-linking/index.html
  added: 2026-05-20
  notes: |
    /wiki:ingest invoked with target wiki/patterns/cluster-linking-observability.md (pattern template).
    Article 5 of the observability expansion. DR/RPO/RTO observability for CL deployments. Covers
    mirror lag (CC Metrics API + CLI PartitionMirrorLag + CP JMX), time-based lag derivation,
    mirror topic state machine (PENDING_STOPPED/STOPPED/SOURCE_UNAVAILABLE), per-SLA-tier
    alert thresholds aligned to ADR-008, failover-readiness checklist. MCP-validated mirror
    state machine + cluster_link_destination_response_bytes; 2 ⚠️ unverified markers on exact
    mirror-lag metric ID and CP self-managed CL JMX MBean. confidence: medium.
  compiled: 2026-05-20
  wiki_articles:
    - wiki/patterns/cluster-linking-observability.md

- path: raw/repos/fsi-dsp/observability/grafana/README.md
  source_url: |
    raw/repos/fsi-dsp/observability/grafana/README.md
    raw/repos/fsi-dsp/observability/grafana/jmx-exporter-config.yaml
    https://docs.confluent.io/operator/current/co-monitor-cp.html
    https://docs.confluent.io/operator/current/co-deploy-cfk.html
    https://github.com/confluentinc/jmx-monitoring-stacks/tree/main/jmxexporter-prometheus-grafana/cfk
  added: 2026-05-20
  notes: |
    /wiki:ingest invoked with target wiki/patterns/cfk-observability-baseline.md (pattern template).
    Article 4 of the observability expansion. Canonical Prometheus + JMX exporter + Grafana wiring
    for CFK deployments. Covers spec.metrics CR fields, Vault-injected JMX credentials with file
    permissions (0600/0644), ServiceMonitor scrape with mTLS, JMX exporter rule set, Grafana
    dashboard provisioning, log aggregation patterns, FSI-tier hardening overlay. MCP validation
    confirmed CFK Helm install pattern, bundled confluentinc/cp-enterprise-prometheus:2.0.0 sidecar,
    Vault sidecar JMX injection with annotation set + file permissions, spec.metrics CRD fields.
    confidence: high.
  compiled: 2026-05-20
  wiki_articles:
    - wiki/patterns/cfk-observability-baseline.md

- path: <none — MCP-only ingest, no rich raw source>
  source_url: |
    https://docs.confluent.io/platform/current/schema-registry/monitoring.html
    https://docs.confluent.io/cloud/current/monitoring/metrics-api.html
  added: 2026-05-20
  notes: |
    /wiki:ingest invoked with target wiki/concepts/schema-registry-observability.md (concept template).
    Article 3 of the observability expansion. CC + self-managed SR observability. MCP-validated
    via confluent-docs schema-registry/monitoring.html: confirmed three SR MBeans
    (kafka.schema.registry:type={jetty-metrics, master-slave-role, jersey-metrics}) and full
    attribute sets. CC SR via Metrics API: io.confluent.kafka.schema_registry/schema_count.
    Article documents the deployment-model gap explicitly and includes a client-side wrapper
    pattern as the compensating signal for CC tenants. One ⚠️ unverified marker on CC managed
    SR per-tenant API rate-limit thresholds. confidence: high.
  compiled: 2026-05-20
  wiki_articles:
    - wiki/concepts/schema-registry-observability.md

- path: raw/repos/fsi-dsp/observability/grafana/jmx-exporter-config.yaml
  source_url: |
    raw/repos/fsi-dsp/observability/grafana/jmx-exporter-config.yaml
    https://kafka.apache.org/documentation/#monitoring
    https://docs.confluent.io/platform/current/kafka/monitoring.html
  added: 2026-05-20
  notes: |
    /wiki:ingest invoked with target wiki/concepts/confluent-platform-broker-jmx.md (concept template).
    Article 2 of the observability expansion. Canonical broker JMX MBean reference for self-managed
    deployments. Expands the 9 MBeans verified in the fsi-dsp Grafana JMX exporter config into the
    full canonical broker MBean tree organized by subsystem (Replication+ISR, Throughput, Network
    request-stages, FetcherLag, Controller, Storage). Includes per-tier alert threshold matrix and
    Prometheus JMX exporter rule excerpt. The 9 source MBeans production-validated; extended set
    well-established in upstream Apache Kafka monitoring docs but not re-MCP-validated. Two
    ⚠️ unverified markers on MessageConversionsTimeMs and KRaft-only controller MBeans.
    confidence: medium.
  compiled: 2026-05-20
  wiki_articles:
    - wiki/concepts/confluent-platform-broker-jmx.md

- path: raw/repos/fsi-dsp/observability/metrics-mapping.md
  source_url: |
    raw/repos/fsi-dsp/observability/metrics-mapping.md
    https://docs.confluent.io/cloud/current/monitoring/metrics-api.html
    https://docs.confluent.io/cloud/current/monitoring/metrics-reference.html
  added: 2026-05-20
  notes: |
    /wiki:ingest invoked with target wiki/concepts/observability-metrics-mapping.md (concept template).
    Article 1 (the spine) of the observability expansion. Cross-provider mapping table (CC Metrics
    API + JMX MBean → PromQL / DQL / SPL / NRQL / Datadog / Instana) grouped by Cluster Health,
    Consumer Lag, Connect Status, DR Readiness, Flink Jobs, plus SR and ksqlDB metric families.
    Provider decision matrix and per-provider ingestion endpoints. Acts as the spine for the
    five follow-on articles.

    MCP validation (confluent-docs metrics-api.html, fetched 2026-05-20): confirmed CC Metrics
    API namespace structure (io.confluent.kafka.server/*, io.confluent.flink/*,
    io.confluent.kafka.connect/*, io.confluent.kafka.ksql/*, io.confluent.kafka.schema_registry/*)
    and the following metric names: active_connection_count, request_count, consumer_lag_offsets,
    received_bytes, sent_bytes, retained_bytes, num_records_in, num_records_out, pending_records,
    compute_pool_utilization, statement_status, received_records (Connect), schema_count (SR),
    full ksqlDB metric family.

    Three ⚠️ unverified markers: (1) cluster_link_mirror_topic_offset_lag exact name (CL family
    confirmed but exact mirror-lag identifier needs revalidation), (2) partition_count and
    successful_authentication_count CC names (may have moved namespace), (3) current_cfu / max_cfu
    likely consolidated into compute_pool_utilization. Provider-specific query syntax sourced
    verbatim from the fsi-dsp repo, not re-validated against current provider docs.
    confidence: medium.
  compiled: 2026-05-20
  wiki_articles:
    - wiki/concepts/observability-metrics-mapping.md

- path: <none — MCP-only ingest, fulfills auto-stub from /review>
  source_url: |
    outputs/reports/oic-cc-acks-all-timeouts-review-2026-04-29.md (26 claim validations)
    wiki/_queue.md Auto-Stubs section (oic-kafka-integration | Date: 2026-04-29 | Source: oic_cc_acks_all_timeouts.md)
    https://kafka.apache.org/41/configuration/producer-configs/
  added: 2026-05-18
  notes: |
    /wiki:ingest invoked with target wiki/concepts/oic-kafka-integration.md. Fulfills the
    auto-stub queued from /review (2026-04-29). Concept article on Oracle Integration Cloud
    Kafka adapter → Confluent Cloud integration. Covers Connectivity Agent architecture
    (JVM hop in OCI publishing cross-cloud to CC on Azure/AWS), GZIP-only compression
    constraint, partial Additional-Properties passthrough (the Critical-severity premise
    flagged in the /review Premise Challenge), cross-cloud OCI→Azure RTT timeout overrides
    on the FSI producer baseline (request.timeout.ms=60000, delivery.timeout.ms=120000
    with the corrected `>= linger.ms + request.timeout.ms` rule, retry.backoff.ms=1000,
    linger.ms=50, batch.size=65536, connections.max.idle.ms=180000), Azure ILB silent-kill
    mitigation cross-linked to azure-connection-management, CC cluster-side settings,
    three-layer acks=all timeout triage tree (producer JMX / cluster ISR / network RTT),
    and EOS implications under uncertain transactional.id support. Source raw file
    (oic_cc_acks_all_timeouts.md) not present in raw/articles/; ingest sourced from the
    already-validated /review report with all 26 claim verdicts and the corrections
    applied inline (delivery.timeout rule fixed; GZIP "default" attribution clarified).
    Three inline ⚠️ unverified markers retained: (1) GZIP-only behavior of the OIC adapter
    (operationally reported; Oracle product, not surfaced in confluent-docs), (2) Oracle's
    honored/overridden/ignored property matrix, (3) OIC Kafka adapter transactional.id
    support. confidence: medium pending Oracle-side authoritative confirmation.
  compiled: 2026-05-18
  wiki_articles:
    - wiki/concepts/oic-kafka-integration.md

- path: kafka-best-practices.md
  added: 2026-04-17
  notes: |
    Kafka best-practices notes covering broker, producer, consumer, app-level, and monitoring guidance. /wiki:ingest invoked with target
    wiki/patterns/latency-optimized-kafka-client.md. Raw source file NOT present in
    raw/articles/ at compile time (file referenced in queue but absent on disk). Article
    compiled via MCP-only path: cloud-agnostic latency baseline drawing on the
    already-MCP-validated companion article wiki/concepts/azure-connection-management.md
    (last_validated 2026-05-18) and the existing Azure-specific pattern
    wiki/patterns/low-latency-kafka-azure.md. confluent-docs producer-configs fetch
    succeeded but the page was too large to inline-grep within budget; key default
    values cited (linger.ms, batch.size, fetch.min.bytes=1 canonical, max.poll.records=500,
    connections.max.idle.ms=540000, reconnect.backoff.max.ms=1000) cross-checked against
    the validated companion article. Two inline ⚠️ unverified markers: (1) Kafka 4.0
    linger.ms KIP-1083 default change to 5ms (widely documented but not re-fetched in
    this session), (2) cross-flag against the existing low-latency-kafka-azure article
    incorrectly citing fetch.min.bytes default as 1024 (AK canonical is 1 byte) — that
    article should be reconciled in a future /wiki:validate pass. confidence: medium.
  compiled: 2026-05-18
  wiki_articles:
    - wiki/patterns/latency-optimized-kafka-client.md

- path: kafka-recommendations.md
  added: 2026-04-17
  notes: |
    End-to-end latency triage/remediation notes, intended as source for outputs/reports/ and wiki stubs on azure-connection-management
    and latency-optimized-kafka-client. Raw source file NOT present in raw/articles/ at
    compile time. Per the ingest-queue note this was always intended to land primarily as
    a report in outputs/reports/ (not a wiki article), with wiki coverage handled by the
    azure-connection-management concept (already compiled 2026-05-18) and the new
    latency-optimized-kafka-client pattern. Marking processed to clear the pending queue;
    the report side of this entry is not produced (no raw input available to render).
    Wiki coverage of the underlying triage tree is provided by:
      - wiki/concepts/azure-connection-management.md (ILB silent-kill)
      - wiki/patterns/low-latency-kafka-azure.md (Azure overlay)
      - wiki/patterns/latency-optimized-kafka-client.md (cloud-agnostic baseline)
  compiled: 2026-05-18
  wiki_articles:
    - wiki/patterns/latency-optimized-kafka-client.md
    - wiki/concepts/azure-connection-management.md
    - wiki/patterns/low-latency-kafka-azure.md

- path: <none — MCP-only ingest, fulfills _queue.md stub>
  source_url: |
    wiki/_queue.md Stubs to Create line 14 (Flink Event Routing — raw → Flink → derived canonical pattern)
    wiki/patterns/flink-runtime-models.md (already-validated companion — runtime context, state-TTL semantics)
    wiki/concepts/flink-confluent-cloud-setup.md (already-validated companion — compute pools, statement lifecycle, autopilot)
    wiki/patterns/cdc-to-tableflow-flink-decode.md (already-validated companion — specific CDC instance of the pattern)
    wiki/patterns/connect-deployment-models.md (where SMT routing lives in the anti-pattern architecture)
    wiki/concepts/schema-registry-best-practices.md (CSFLE-at-SR exception for the producer-side PII case)
  added: 2026-05-18
  notes: |
    /wiki:ingest invoked with target wiki/patterns/flink-event-routing.md. Pattern article on
    the canonical raw → stateless Flink statement → derived topic shape: replayability via
    scan.startup.mode=earliest-offset, schema decoupling from upstream wire format, debuggability
    via preserved raw topic. Documents the stateless-vs-stateful operator boundary (filter,
    projection, JSON_VALUE, lookup join, temporal join = OK; regular join, non-windowed agg,
    COUNT DISTINCT = NOT a routing pattern, inherits state-TTL caveats), the multi-INSERT split
    idiom, CC compute-pool sizing for stateless routing, and the producer-side anti-pattern
    (Connect SMTs, app-side branching, Debezium predicates, producer flattening, pre-filtered
    fan-out) with the narrow CSFLE-at-SR exception for PII. MCP-only ingest leveraging the
    already-validated companion articles flink-runtime-models (last_validated 2026-05-13),
    flink-confluent-cloud-setup (last_validated 2026-05-15), and cdc-to-tableflow-flink-decode
    (last_validated 2026-05-16). One inline ⚠️ unverified marker on per-CFU throughput ceilings
    for stateless routing — sizing heuristic calibrated against flink-runtime-models defaults
    rather than published per-CFU numbers. confidence: medium.
  compiled: 2026-05-18
  wiki_articles:
    - wiki/patterns/flink-event-routing.md

- path: <none — MCP-only ingest, fulfills _queue.md stub>
  source_url: |
    wiki/_queue.md Stubs to Create line 17 (DR Application Routing — client-plane DR pattern)
    outputs/reports/wiki-validation-2026-05-15.md (ORKA §5.1 resolution — Kroxylicious FetchResponseFilter protocol confirmation)
    outputs/reports/wiki-validation-2026-05-18-orka-guarantees.md (ORKA §5.3 resolution — workload-class discriminator)
    wiki/concepts/confluent-cloud-gateway.md (existing concept article — companion product view)
    wiki/patterns/dr-cluster-linking.md (Consul KV flip pattern referenced as Solution 1)
  added: 2026-05-18
  notes: |
    /wiki:ingest invoked with target wiki/patterns/dr-application-routing.md. Pattern article
    covering the client-plane gap that data-plane DR (CL/MM2/MRC) does not solve: how clients
    find the surviving cluster after failover. Three solution classes documented (DNS abstraction
    via Consul, protocol proxy via Confluent Gateway / ORKA / Kroxylicious, CC One-Click DR) with
    a decision matrix on RTO, restart requirement, advertised-listener config, consumer-pause
    semantics, auth swapping, stateless vs stateful correctness, vendor-contract surface, and
    topology fit (CC-only / CFK / hybrid). The load-bearing piece — per the two resolved
    validation reports — is the explicit workload-class discriminator: stateless consumers are
    correct under all three solutions given planned `promote` + CL offset-sync; stateful apps
    (Streams / ksqlDB / Flink-with-state) are NOT generally correct under any of them because
    the state surface is outside CL's replication boundary. ORKA-specific stateful-preservation
    claims explicitly NOT attributed (vendor-internal per §5.1 and §5.3 reports; requires
    GoodLabs disclosure to author). Inline ⚠️ unverified marker on the One-Click DR GA/surface
    area pending current confluent-docs revalidation (the relevant Cloud Gateway DR pages
    returned 302 redirects in the 2026-05-18 validation pass). confidence: medium.
  compiled: 2026-05-18
  wiki_articles:
    - wiki/patterns/dr-application-routing.md

- path: <none — MCP-only ingest, fulfills _queue.md stub>
  source_url: |
    wiki/_queue.md Stubs to Create line 16 (Confluent Gateway protocol-aware proxy)
    Attempted MCP fetches (all returned 302 → docs.confluent.io/index.html):
      https://docs.confluent.io/platform/current/kafka/gateway/overview.html
      https://docs.confluent.io/gateway/current/overview.html
      https://docs.confluent.io/cloud/current/networking/gateway/overview.html
      https://docs.confluent.io/platform/current/gateway/overview.html
      https://docs.confluent.io/operator/current/co-gateway.html
      https://docs.confluent.io/confluent-gateway/current/overview.html
  added: 2026-05-18
  notes: |
    /wiki:ingest invoked with target wiki/concepts/confluent-cloud-gateway.md. Concept
    article on Confluent Gateway — the self-managed protocol-aware Kafka proxy (CFK/Docker)
    for custom domains, auth swapping, traffic control, fencing/unfencing, and DR client
    switchover without restart. Disambiguates from the Confluent Cloud Ingress
    PrivateLink Gateway (covered in concepts/private-networking.md). MCP direct-URL
    fetches for Confluent Gateway docs returned 302 redirects (product is real but
    canonical doc URL not discoverable from llms.txt index in this session). Authored
    from the queue stub description + cross-references to the resolved ORKA/proxy DR
    validation reports (outputs/reports/wiki-validation-2026-05-15.md and
    wiki-validation-2026-05-18-orka-guarantees.md). Inline ⚠️ unverified markers on:
    (1) the 1.1.0 GA / CPC Gateway 1.2 version-feature pairing, (2) exact CFK CRD
    naming, (3) the 1.5–2× sizing heuristic. confidence: medium pending a
    /wiki:validate pass once the Confluent Gateway doc URL is locatable.
  compiled: 2026-05-18
  wiki_articles:
    - wiki/concepts/confluent-cloud-gateway.md

- path: <none — MCP-only ingest, fulfills auto-stub from /review>
  source_url: |
    https://docs.confluent.io/cloud/current/topics/tableflow/overview.html
    outputs/reports/confluent-best-practices-quickstart.md (Part VII — Tableflow)
    wiki/_queue.md auto-stub (Date: 2026-05-12) under Auto-Stubs
  added: 2026-05-18
  notes: |
    /wiki:ingest invoked with target wiki/concepts/tableflow-iceberg-delta.md. Concept-level
    framework article complementing the existing tableflow trip-wires
    (concepts/tableflow-changelog-mode-immutability) and the CDC pattern
    (patterns/cdc-to-tableflow-flink-decode). Validated against confluent-docs MCP
    (Tableflow overview page) on 2026-05-18: formats (Iceberg + Delta Lake), GA status,
    Schema Registry as source-of-truth, supported encodings (Avro/Protobuf/JSON Schema),
    automatic compaction + snapshot bounds (min 10 / max 100), catalog targets
    (AWS Glue, Databricks Unity, Apache Polaris, Snowflake Open Catalog, built-in IRC),
    storage models (managed vs BYOS, Delta-only BYOS), and the AWS+Azure-only / not-GCP /
    not-CP availability surface. One inline ⚠️ unverified marker on the BYOB→BYOS
    terminology correction (source quickstart used BYOB; docs canonically use BYOS).
    confidence: high.
  compiled: 2026-05-18
  wiki_articles:
    - wiki/concepts/tableflow-iceberg-delta.md

- path: <none — MCP-only ingest, concept companion to existing pattern>
  source_url: |
    https://docs.confluent.io/platform/current/connect/index.html
    https://docs.confluent.io/cloud/current/connectors/overview.html
    wiki/patterns/connect-deployment-models.md (existing MCP-validated pattern)
    wiki/_queue.md auto-stub from /review on 2026-05-12 (source: outputs/reports/confluent-best-practices-quickstart.md)
  added: 2026-05-18
  notes: |
    /wiki:ingest invoked with target wiki/concepts/kafka-connect-deployment-models.md.
    Fulfills the auto-stub queued from /review (2026-05-12). Companion concept article to
    the existing wiki/patterns/connect-deployment-models.md: pattern covers operational
    decision matrix + tuning + triage; this concept article covers framework-level
    architecture (workers, connectors, tasks, converters, SMTs, internal topics,
    standalone vs distributed, KIP-618 EOS source, source vs sink lifecycle, the three
    Confluent deployment models as architecture). MCP validation partial — confluent-docs
    Connect overview pages exceeded fetch token limits; relied on the already-validated
    pattern article + well-established Connect framework knowledge. One inline
    ⚠️ unverified marker on current CC Custom Connector + PrivateLink support
    compatibility (subject to product evolution). confidence: medium pending a
    /wiki:validate pass.
  compiled: 2026-05-18
  wiki_articles:
    - wiki/concepts/kafka-connect-deployment-models.md

- path: <none — MCP-only ingest>
  source_url: |
    https://docs.confluent.io/cloud/current/networking/aws-platt.md
    https://docs.confluent.io/cloud/current/networking/azure-platt.md
    https://docs.confluent.io/cloud/current/networking/gcp-platt.md
    https://docs.confluent.io/cloud/current/networking/private-links/aws-privatelink-gateway.md
    https://docs.confluent.io/cloud/current/networking/private-links/azure-privatelink-gateway.md
    https://docs.confluent.io/cloud/current/networking/private-links/gcp-private-service-connect-gateway.md
    https://docs.confluent.io/cloud/current/flink/concepts/flink-private-networking.md
    https://docs.confluent.io/cloud/current/flink/concepts/flink-private-networking-egress.md
  added: 2026-05-15
  notes: |
    /wiki:ingest invoked with target wiki/concepts/private-networking.md and the
    following topic anchors: PrivateLink Gateway (replacing PLATT, AWS 2026-02-12 /
    Azure+GCP 2026-05-04), Azure/AWS/GCP Private Link setup, Enterprise vs Dedicated
    cluster requirements, Flink-to-Kafka internal routing (gateway covers client→Flink
    only; Flink↔Kafka stays on Confluent fabric), egress PrivateLink for external
    services (AWS/Azure only — no GCP), and the Azure ILB idle-timeout bypass via
    Private Link. No raw/ source file — content compiled directly from confluent-docs
    MCP pages (PLATT pages per cloud, PrivateLink Gateway pages per cloud, Flink
    private-networking ingress and egress pages). All claims validated against those
    MCP sources except the Azure ILB idle-timeout default/max values, which carry an
    inline ⚠️ unverified tag (architectural claim — that Private Link bypasses the
    ILB — is sound; specific timeout numbers should be reconfirmed via current Azure
    docs before customer-facing use). confidence: high.
  compiled: 2026-05-15
  wiki_articles:
    - wiki/concepts/private-networking.md

- path: <none — MCP-only ingest>
  source_url: |
    https://docs.confluent.io/cloud/current/flink/overview.md
    https://docs.confluent.io/cloud/current/flink/concepts/compute-pools.md
    https://docs.confluent.io/cloud/current/flink/concepts/statements.md
    https://docs.confluent.io/cloud/current/flink/concepts/autopilot.md
    https://docs.confluent.io/cloud/current/flink/concepts/schema-statement-evolution.md
    https://docs.confluent.io/cloud/current/flink/concepts/timely-stream-processing.md
    https://docs.confluent.io/cloud/current/flink/operate-and-deploy/flink-rbac.md
  added: 2026-05-15
  notes: |
    /wiki:ingest invoked with target wiki/concepts/flink-confluent-cloud-setup.md and
    seven topic anchors (compute pools, catalog/db/table mapping, dual-plane RBAC,
    statement lifecycle, Autopilot, watermarks, statement evolution + carry-over
    offsets). No raw/ source file — content compiled directly from confluent-docs MCP
    pages (CC Flink overview, compute pools, statements, autopilot, schema-statement
    evolution, timely-stream-processing, flink-rbac). All verifiable claims validated
    against those MCP pages. confidence: high.
  compiled: 2026-05-15
  wiki_articles:
    - wiki/concepts/flink-confluent-cloud-setup.md

- path: raw/articles/shared-schema-howto.md
  added: 2026-05-15
  notes: |
    FSI shared-types library walk-through (Money, CustomerId, UsAddress, payments-value
    referencing both). Compiled into a new pattern article covering library layout,
    schema references mechanics (name+subject+exact version, registered first, pinned),
    Schema Registry ID assignment behavior, and the FULL_TRANSITIVE → BACKWARD_TRANSITIVE
    interaction across shared and domain subjects. Source-specific names were replaced with
    placeholders ("FSI firm" / `com.fsifirm.common` namespace) per ingest args. Validated schema
    references mechanics and subject-version-ID semantics via confluent-docs
    (Confluent Platform serdes-develop, schema-references and subject-name-strategy
    sections).
  compiled: 2026-05-15
  wiki_articles:
    - wiki/patterns/schema-registry-shared-types.md

- path: outputs/reports/confluent-best-practices-quickstart.md
  added: 2026-05-13
  notes: |
    786-line FSI-flavored quickstart spanning producers, consumers, topics/clusters
    (CC vs CP), Schema Registry, Connect, Flink, Tableflow, K8s/CFK, security,
    networking, capacity planning, triage tree, and Top-20-gotchas appendix.
    Validated via /review (outputs/reports/confluent-best-practices-quickstart-review-2026-05-12.md).
    Split into 8 focused articles per ingest routing hints. Recency-sensitive
    items (CC cluster/Freight specs, per-CKU limits, Tableflow GA surface,
    KIP-848 client matrix, Custom Connector on PrivateLink) flagged inline
    with ⚠️ unverified; confidence set to medium pending an MCP revalidation
    pass via /wiki:validate.
    fsi-dsp follow-up still pending: verify
    reference/java-producer/FsiProducer.java and reference/java-consumer/FsiConsumer.java
    exist in fsi-dsp; propose PRs if not.
  compiled: 2026-05-13
  wiki_articles:
    - wiki/patterns/producer-config-fsi.md
    - wiki/patterns/consumer-config-fsi.md
    - wiki/concepts/cc-cluster-tiers.md
    - wiki/concepts/schema-registry-best-practices.md
    - wiki/patterns/connect-deployment-models.md
    - wiki/patterns/flink-runtime-models.md
    - wiki/concepts/network-connectivity-by-tier.md
    - wiki/synthesis/confluent-gotchas-top-20.md

- path: raw/repos/fsi-dsp/README.md
  source_url: https://github.com/goodlabs-studio/fsi-dsp
  notes: Top-level platform overview — compile into wiki/concepts/ and wiki/patterns/
  compiled: 2026-04-11
  wiki_articles:
    - wiki/concepts/fsi-data-streaming-platform.md
    - wiki/patterns/fsi-governance-automation.md

- path: raw/repos/fsi-dsp/docs/dr-runbook.md
  notes: DR procedures for CL, MM2, MRC — compile into wiki/patterns/dr-*
  compiled: 2026-04-11
  wiki_articles:
    - wiki/patterns/dr-cluster-linking.md
    - wiki/patterns/dr-mirrormaker2.md
    - wiki/patterns/dr-multi-region-cluster.md

- path: raw/repos/fsi-dsp/docs/schema-guide.md
  notes: Schema naming, compatibility, evolution — expand wiki/concepts/schema-evolution-strategies.md
  compiled: 2026-04-11
  wiki_articles:
    - wiki/concepts/schema-evolution-strategies.md

- path: raw/repos/fsi-dsp/docs/compliance-guide.md
  notes: FSI regulatory reference — new wiki/concepts/fsi-compliance.md
  compiled: 2026-04-11
  wiki_articles:
    - wiki/concepts/fsi-compliance.md

- path: raw/repos/fsi-dsp/ansible/vars/sla_tiers.yml
  notes: SLA tier definitions — new wiki/concepts/sla-tiers.md
  compiled: 2026-04-11
  wiki_articles:
    - wiki/concepts/sla-tiers.md

- path: raw/repos/fsi-dsp/ansible/vars/naming_rules.yml
  notes: Topic naming rules — expand wiki/concepts/ or new wiki/patterns/topic-naming.md
  compiled: 2026-04-11
  wiki_articles:
    - wiki/patterns/topic-naming.md

- path: raw/repos/fsi-dsp/docs/adr
  notes: Compile all ADRs into wiki/synthesis/adr-index.md with summaries
  compiled: 2026-04-11
  wiki_articles:
    - wiki/synthesis/adr-index.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-streams-programming/references/topology-patterns.md
  added: 2026-05-16
  notes: |
    Parent article #1 of 10 (H.1). Target: wiki/patterns/kafka-streams-topology-patterns.md (pattern template).
    Frontmatter: extend with `source: confluent-agent-skills@91d1871ef8c320be92bca955c8e42492a2778cb4`
    and `upstream_path: skills/kafka-streams-programming/references/topology-patterns.md`.
    Provenance footer per CONTEXT.md D-03 shape.
    Confidence: high via source attestation (D-07) — skip the full MCP re-validation gate; upstream evals
    gate at 90%+ before merge so source attestation suffices. /wiki:ingest Step 3d remains for cross-link
    accuracy but does not block confidence: high.
    related: cross-link to existing wiki articles where natural (e.g., concepts/exactly-once-semantics,
    patterns/dr-cluster-linking) plus the trip-wires this article seeds (#4, #5, #6).
  compiled: 2026-05-16
  wiki_articles:
    - wiki/patterns/kafka-streams-topology-patterns.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-streams-programming/references/debugging.md
  added: 2026-05-16
  notes: |
    Parent article #2. Target: wiki/concepts/kafka-streams-debugging.md (concept template).
    Extend frontmatter with source/upstream_path. confidence: high via source attestation (D-07).
    Seeds trip-wires #4 (uncaught-exception-handler-import), #5 (avro-schema-source-directory),
    #6 (schema-aware-console-producer). related: cross-link to those trip-wire articles via `related:`.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/concepts/kafka-streams-debugging.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-streams-programming/references/production-hardening.md
  added: 2026-05-16
  notes: |
    Parent article #3. Target: wiki/concepts/kafka-streams-production-hardening.md (concept).
    Extend frontmatter with source/upstream_path. confidence: high via source attestation.
    related: cross-link to concepts/exactly-once-semantics, patterns/producer-config-fsi,
    patterns/consumer-config-fsi.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/concepts/kafka-streams-production-hardening.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-streams-programming/references/schema-patterns.md
  added: 2026-05-16
  notes: |
    Parent article #4. Target: wiki/concepts/kafka-streams-schema-patterns.md (concept).
    Extend frontmatter. confidence: high via source attestation.
    related: concepts/schema-registry-best-practices, concepts/schema-evolution-strategies,
    patterns/schema-registry-shared-types.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/concepts/kafka-streams-schema-patterns.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-streams-programming/references/config-baseline.md
  added: 2026-05-16
  notes: |
    Parent article #5. Target: wiki/concepts/kafka-streams-config-baseline.md (concept).
    Extend frontmatter. confidence: high via source attestation.
    related: patterns/producer-config-fsi, patterns/consumer-config-fsi.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/concepts/kafka-streams-config-baseline.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-streams-programming/references/architecture.md
  added: 2026-05-16
  notes: |
    Parent article #6. Target: wiki/concepts/kafka-streams-architecture.md (concept).
    Extend frontmatter. confidence: high via source attestation.
    related: concepts/fsi-data-streaming-platform, concepts/exactly-once-semantics,
    patterns/flink-runtime-models.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/concepts/kafka-streams-architecture.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/confluent-cloud-cdc-tableflow/references/flink-sql-patterns.md
  added: 2026-05-16
  notes: |
    Parent article #7. Target: wiki/patterns/cdc-to-tableflow-flink-decode.md (pattern).
    Extend frontmatter (upstream_path: skills/confluent-cloud-cdc-tableflow/references/flink-sql-patterns.md).
    confidence: high via source attestation.
    Seeds trip-wires #1 (tableflow-changelog-mode-immutability), #2 (cdc-tableflow-flink-decode-required).
    related: concepts/exactly-once-semantics, concepts/flink-checkpointing,
    concepts/flink-confluent-cloud-setup, and the two trip-wire descendants.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/patterns/cdc-to-tableflow-flink-decode.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/confluent-cloud-cdc-tableflow/references/connector-configs.md
  source_url: |
    Also merges:
      raw/vendor/confluent-agent-skills/91d1871e/skills/confluent-cloud-cdc-tableflow/references/database-prerequisites.md
      raw/vendor/confluent-agent-skills/91d1871e/skills/confluent-cloud-cdc-tableflow/references/troubleshooting.md
  added: 2026-05-16
  notes: |
    Parent article #8 — THREE-WAY MERGE into a single wiki/concepts/cdc-source-connector-setup.md.
    Section ordering (Claude's Discretion per CONTEXT.md): (1) Database prerequisites first, (2) Connector
    config recipes second, (3) Troubleshooting last as a triage table — mirrors operational reading order
    (pre-deploy → deploy → debug). Cite all three upstream_paths in frontmatter as a yaml list:
      upstream_path:
        - skills/confluent-cloud-cdc-tableflow/references/connector-configs.md
        - skills/confluent-cloud-cdc-tableflow/references/database-prerequisites.md
        - skills/confluent-cloud-cdc-tableflow/references/troubleshooting.md
    Provenance footer should list all three files. Seeds trip-wire #3 (oracle-xstream-source-limitations).
    confidence: high via source attestation. related: patterns/cdc-to-tableflow-flink-decode,
    patterns/connect-deployment-models.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/concepts/cdc-source-connector-setup.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-schema-registry/references/detection-patterns.md
  source_url: |
    Also merges:
      raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-schema-registry/references/code-migration.md
  added: 2026-05-16
  notes: |
    Parent article #9 — TWO-WAY MERGE into wiki/patterns/schema-registry-adoption-playbook.md (pattern).
    Section ordering: (1) Detection patterns first (scan existing Kafka usage), (2) Code migration second
    (Terraform generation + producer/consumer migration). upstream_path is a yaml list of both files.
    Provenance footer lists both. confidence: high via source attestation.
    related: concepts/schema-registry-best-practices, concepts/schema-evolution-strategies,
    patterns/fsi-governance-automation.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/patterns/schema-registry-adoption-playbook.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-schema-registry/references/schema-inference.md
  source_url: |
    Also merges:
      raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-schema-registry/references/categorization.md
  added: 2026-05-16
  notes: |
    Parent article #10 — TWO-WAY MERGE into wiki/concepts/schema-inference-and-pii-categorization.md (concept).
    Section ordering: (1) Schema inference (deriving Avro from data samples), (2) Categorization (PII
    tagging on inferred schemas). upstream_path lists both. Provenance footer lists both.
    confidence: high via source attestation.
    related: concepts/schema-registry-best-practices, concepts/fsi-compliance,
    patterns/schema-registry-shared-types.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/concepts/schema-inference-and-pii-categorization.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/confluent-cloud-cdc-tableflow/SKILL.md
  added: 2026-05-16
  notes: |
    Trip-wire #1 (H.1). Authored via full MCP-validation gate (D-07): confluent-docs query on Tableflow
    materialization semantics confirmed the immutability behavior (mode cached on first materialize;
    S3 table_path keyed by Kafka topic name; recreate requires deleting both Tableflow and Kafka topics).
    Single-fact-focused, ≤500 words, confidence: high.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/concepts/tableflow-changelog-mode-immutability.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/confluent-cloud-cdc-tableflow/SKILL.md
  added: 2026-05-16
  notes: |
    Trip-wire #2 (H.1). Pattern template. Authored via full MCP-validation gate (D-07): confluent-docs
    query on Tableflow APPEND vs CHANGELOG mode tombstone handling confirmed Debezium emits null-value
    records on DELETE and Tableflow APPEND suspends on the first null. Canonical Flink decode pattern
    is the load-bearing remediation. Single-fact-focused, ≤500 words, confidence: high.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/patterns/cdc-tableflow-flink-decode-required.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/confluent-cloud-cdc-tableflow/SKILL.md
  added: 2026-05-16
  notes: |
    Trip-wire #3 (H.1). Authored via full MCP-validation gate (D-07): confluent-docs query on
    OracleXStreamSource connector config confirmed `after.state.only` is not supported. Workaround is
    a Flink projection on the source topic (covered by the canonical decode pattern).
    Single-fact-focused, ≤500 words, confidence: high.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/concepts/oracle-xstream-source-limitations.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-streams-programming/SKILL.md
  source_url: also-cite. raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-streams-programming/evals/evals.json
  added: 2026-05-16
  notes: |
    Trip-wire #4 (H.1). Authored via full MCP-validation gate (D-07): confluent-docs query on KS 4.x
    package structure confirmed StreamsUncaughtExceptionHandler lives at org.apache.kafka.streams.errors
    (not nested under KafkaStreams as in 2.8-3.x). evals.json file is NOT vendored per D-02 — cited
    in body prose as upstream-eval evidence; upstream_path frontmatter cites the SKILL.md sibling.
    Single-fact-focused, ≤500 words, confidence: high.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/concepts/kafka-streams-4x-uncaught-exception-handler-import.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-streams-programming/SKILL.md
  source_url: also-cite. raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-streams-programming/evals/evals.json
  added: 2026-05-16
  notes: |
    Trip-wire #5 (H.1). Authored via full MCP-validation gate (D-07): context7 query on Avro Maven
    Plugin canonical layout confirmed src/main/avro/ as the default sourceDirectory; confluent-docs
    fallback confirmed parity with the Confluent Schema Registry Maven plugin and Gradle Avro plugin.
    evals.json file is NOT vendored per D-02 — cited in body prose; upstream_path is the SKILL.md sibling.
    Single-fact-focused, ≤500 words, confidence: high.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/concepts/avro-schema-source-directory.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-streams-programming/SKILL.md
  source_url: also-cite. raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-streams-programming/evals/evals.json
  added: 2026-05-16
  notes: |
    Trip-wire #6 (H.1). Authored via full MCP-validation gate (D-07): confluent-docs query on
    kafka-avro-console-producer CLI usage and the Schema Registry wire format confirmed the 5-byte
    prefix (magic byte + 4-byte schema ID) is required and kafka-console-producer doesn't write it.
    evals.json file is NOT vendored per D-02 — cited in body prose; upstream_path is the SKILL.md.
    Single-fact-focused, ≤500 words, confidence: high.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/concepts/schema-aware-console-producer-required.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/developing-kafka-python-client/SKILL.md
  source_url: also-cite. raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-streams-programming/references/warpstream-optimization.md
  added: 2026-05-16
  notes: |
    Trip-wire #7 (H.1). WarpStream content — context7 fallback (WarpStream is not in confluent-docs per
    vendor-backing rule). MANDATORY verbatim FSI-context paragraph included per CONTEXT.md <specifics>.
    Frontmatter `sources:` lists BOTH vendored paths (python-client SKILL.md + warpstream-optimization.md)
    per Issue 6 fix. Inline ⚠️ unverified marker on the `GET /schemas/types` endpoint claim because
    context7 has limited published coverage of WarpStream's SR endpoint shape; majority of claims
    sourced from upstream confluent-maintained competitive guidance, confidence: high retained.
    Single-fact-focused, ≤500 words.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/concepts/warpstream-schema-registry-format-constraint.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-streams-programming/references/warpstream-optimization.md
  added: 2026-05-16
  notes: |
    Trip-wire #8 (H.1). WarpStream content — context7 fallback. MANDATORY verbatim FSI-context paragraph
    included per CONTEXT.md <specifics>. Inline ⚠️ unverified marker on the internal-replication
    mechanics claim because context7 has limited published coverage of WarpStream's S3-tier internals.
    competitive-context tag set. Single-fact-focused, ≤500 words, confidence: high.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/concepts/warpstream-config-overrides.md

- path: raw/vendor/confluent-agent-skills/91d1871e/skills/kafka-streams-programming/references/warpstream-optimization.md
  added: 2026-05-16
  notes: |
    Trip-wire #9 (H.1). Split-coverage validation per D-07: confluent-docs confirmed classic-Kafka
    EOS half (processing.guarantee=exactly_once_v2 enables idempotent producer; max.in.flight.requests.
    per.connection ≤5 constraint); context7 + upstream WarpStream optimization reference (Confluent-
    maintained) confirmed the WarpStream-specific throughput-cost half. Inline ⚠️ unverified marker on
    the exact 20-40% throughput delta because context7 has limited published coverage of the precise
    numbers. MANDATORY verbatim FSI-context paragraph included. competitive-context tag set.
    Single-fact-focused, ≤500 words, confidence: high.
  compiled: 2026-05-16
  wiki_articles:
    - wiki/concepts/exactly-once-v2-warpstream-throughput-cost.md
