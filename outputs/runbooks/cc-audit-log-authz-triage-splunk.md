---
title: Confluent Cloud Audit-Log Authorization Triage (Splunk)
subtitle: What the audit log actually records — and how to triage it
audience: Platform / C4E (owners), security (retention & investigation)
validated: 2026-07-17 against confluent-docs (CC audit-logging event methods, schema, retention, access) + KIP-679
confidence: high
companion: cc-client-side-authz-denial-triage.md
---

# Confluent Cloud Audit-Log Authorization Triage (Splunk)

**Purpose:** Measure, classify, and act on the authorization and authentication
failures that Confluent Cloud audit logs *actually record*, surfaced in Splunk — and
shift routine triage from the platform team to application teams.

> **Read §1 first.** The single most expensive mistake with CC audit logs is assuming
> they contain your everyday consumer-group and metadata denials. They do not. Building
> triage on `authorizationInfo.granted=false` alone silently misses every producer and
> consumer *topic* denial. The queries here use the correct event types.

---

## 1. What CC audit logs record — the boundary that governs everything

The audit log is a record of **broker-side authentication and authorization decisions
for a specific, enumerated set of request methods.** It is not a record of every
client failure. Three event types matter:

| CloudEvents `type` | Verdict field | Carries |
|---|---|---|
| `io.confluent.kafka.server/authentication` | `data.authenticationInfo.result` (`SUCCESS` / failure) | API-key / SASL validation |
| `io.confluent.kafka.server/authorization` | `data.authorizationInfo.granted` (`true`/`false`) | **Authorization decisions** for admin/lifecycle ops + `mds.Authorize` (SR/Connect/ksqlDB) |
| `io.confluent.kafka.server/request` | `data.result.status` (`SUCCESS`/`FAILURE`) + `data.result.data.errorType` | **Request records**, including `kafka.Produce` / `kafka.Fetch` — this is where produce/consume topic denials live |

### The coverage matrix — what shows where

| Failure | Audited? | Event type / how it appears |
|---|---|---|
| Bad / expired API key | **Yes** | `authentication`, `result != SUCCESS` |
| Producer topic denial (`TOPIC_AUTHORIZATION_FAILED`) | **Yes** | `request`, `kafka.Produce`, `result.status=FAILURE` — **NOT** an `authorization` event |
| Consumer *topic* fetch denial | **Yes, sampled** | `request`, `kafka.Fetch`, FAILURE — **first fetch per connection only** |
| Consumer **group** denial (`GROUP_AUTHORIZATION_FAILED` at JoinGroup) | **No** | Not emitted by either type → see companion runbook |
| `Describe` / `DescribeConfigs` metadata denial | **No** | Not an audited method → see companion runbook |
| Topic/ACL/config lifecycle denial | **Yes** | `authorization`, `granted=false` (`CreateTopics`, `CreateAcls`, `AlterConfigs`, `DeleteTopics`, …) |
| Schema Registry / Connect / ksqlDB authz | **Yes** | `authorization`, `methodName="mds.Authorize"` |
| Network / TLS / PrivateLink / DNS failure | **No** | Below the broker → client logs, cloud network telemetry |

> **Validation note.** Confluent's *Kafka management auditable events* page states the
> management methods share names with the authorization methods **"except for
> `kafka.Fetch` and `kafka.Produce`, which do not generate corresponding authorization
> events."** That single sentence is why produce/consume denials must be queried as
> `request` FAILUREs, not `granted=false`.

**Practical consequence:** a user reporting "can't connect" who appears in *none* of
these queries almost certainly has a **network, DNS, credential-delivery, or
consumer-group** problem — the first three are below the broker, the last is in the
companion runbook. That absence is itself a triage signal: route away from
platform-permissions.

**Baseline window:** build the 7-day baseline from **Splunk's index**, not the topic.
The `confluent-audit-log-events` topic retains only **7 days** (see §5); if the sink
lags or is newly deployed, older history is **unrecoverable** — there is no replay.

---

## 2. Access and ingestion

**Access model (corrected).** There is **no `AuditLogAdmin` role.** An **`OrganizationAdmin`**
creates an API key/secret **bound to the audit log cluster**; *after that, any user can
consume with that key* — no special role required. Treat that key as a broadly-usable
secret: scope its distribution, rotate it, and store it in the secrets manager. In FSI,
prefer **mTLS + RBAC** over API keys per canon; where the audit cluster only exposes a
key, compensate with tight key custody and audit of who holds it.

**Ingestion — pick one:**

- **Option A — Confluent Splunk Sink connector (fully managed).** Runs in the audit-log
  environment against the audit-log cluster with the OrganizationAdmin-minted key, to a
  Splunk HEC endpoint. Set `splunk.hec.json.event.enabled=true` so events land as
  structured JSON, not an escaped string.
- **Option B — Splunk Connect for Kafka (self-managed).** Preferred when the connector
  must run inside an existing network boundary, or Splunk Connect already runs for other
  topics.

**Splunk side:**

```
index      = confluent_audit
sourcetype = confluent:auditlog
```

`props.conf`:
```
[confluent:auditlog]
KV_MODE                 = json
SHOULD_LINEMERGE        = false
TIME_PREFIX             = \"time\":\"
TIME_FORMAT             = %Y-%m-%dT%H:%M:%S.%3NZ
MAX_TIMESTAMP_LOOKAHEAD = 30
TRUNCATE                = 10000
```

Set retention with security; audit data typically outlives application logs.

---

## 3. Key fields

`KV_MODE=json` flattens the CloudEvents envelope. The verdict lives in a **different
place depending on event type** — this is the crux.

| Field | Contents | Applies to |
|---|---|---|
| `type` | `io.confluent.kafka.server/{authentication,authorization,request}` | routing |
| `data.methodName` | `kafka.Produce`, `kafka.Fetch`, `kafka.CreateTopics`, `mds.Authorize`, `kafka.Authentication` | all |
| `data.authenticationInfo.principal` | `User:sa-abc123` | all — map to owning app |
| `data.authenticationInfo.result` | `SUCCESS` / reason | `authentication` |
| `data.authorizationInfo.granted` | `true`/`false` | **`authorization` only** |
| `data.authorizationInfo.operation` | `Create`, `Delete`, `Alter`, `ClusterAction`, … | `authorization` |
| `data.authorizationInfo.resourceType` / `resourceName` / `patternType` | requested resource | authz + request |
| `data.result.status` | `SUCCESS` / `FAILURE` | **`request` only** |
| `data.result.data.errorType` | `TOPIC_AUTHORIZATION_FAILED`, `CLUSTER_AUTHORIZATION_FAILED` | **`request` only** |
| `data.requestMetadata.client_address` | source IP | all |
| `data.rbacAuthorization` / `data.authorizationInfo.rbacAuthorization.role` | role + scope evaluated | RBAC-governed resources |
| `time` | event timestamp | all |

> `rbacAuthorization` and `aclAuthorization` are **fields inside `authorizationInfo`**,
> not event types. (The original runbook listed `mds_authorization` and
> `rbac_authorization` as event types — neither exists.)

---

## 4. Triage queries

### 4.1 Admin / lifecycle / MDS authorization denials
Change-control and privilege-escalation surface: who was denied a topic-create, ACL
change, config alter, or a Schema-Registry/Connect operation.

```spl
index=confluent_audit sourcetype=confluent:auditlog
  type="io.confluent.kafka.server/authorization"
  data.authorizationInfo.granted=false
| rename data.methodName                     AS method,
         data.authenticationInfo.principal   AS principal,
         data.authorizationInfo.operation    AS operation,
         data.authorizationInfo.resourceType AS resource_type,
         data.authorizationInfo.resourceName AS resource_name,
         data.requestMetadata.client_address AS src_ip
| stats count AS denials, dc(resource_name) AS distinct_resources,
        values(resource_name) AS resources, min(_time) AS first_seen, max(_time) AS last_seen
  BY principal, method, operation, resource_type
| eval first_seen=strftime(first_seen,"%F %T"), last_seen=strftime(last_seen,"%F %T")
| sort - denials
```

### 4.2 Producer / consumer topic denials
The everyday data-path denial. **Keyed on `request` + FAILURE, not `granted=false`** —
this is the query the original runbook was missing.

```spl
index=confluent_audit sourcetype=confluent:auditlog
  type="io.confluent.kafka.server/request"
  data.result.status=FAILURE
| rename data.methodName                     AS method,
         data.authenticationInfo.principal   AS principal,
         data.authorizationInfo.resourceName AS resource_name,
         data.result.data.errorType          AS error_type,
         data.requestMetadata.client_address AS src_ip
| search error_type IN ("TOPIC_AUTHORIZATION_FAILED","CLUSTER_AUTHORIZATION_FAILED")
| stats count AS denials, dc(resource_name) AS distinct_resources,
        values(resource_name) AS resources, min(_time) AS first_seen, max(_time) AS last_seen
  BY principal, method, error_type
| eval first_seen=strftime(first_seen,"%F %T"), last_seen=strftime(last_seen,"%F %T")
| sort - denials
```

> **`kafka.Fetch` is sampled — first fetch per connection only.** A consumer stuck in a
> denial-retry loop on one connection shows up **once**, not thousands of times. Do not
> read low `kafka.Fetch` denial counts as low impact; corroborate with the client side.

### 4.3 Failure-class distribution (7-day baseline)
Runs across **both** event types so the picture is complete. Establish the shape before
changing any permission.

```spl
index=confluent_audit sourcetype=confluent:auditlog earliest=-7d@d
  ( (type="io.confluent.kafka.server/authorization" data.authorizationInfo.granted=false)
    OR (type="io.confluent.kafka.server/request" data.result.status=FAILURE) )
| rename data.methodName                   AS method,
         data.authenticationInfo.principal AS principal,
         data.result.data.errorType        AS error_type,
         data.authorizationInfo.operation  AS operation
| eval class = case(
    method=="kafka.Produce",                                        "P: Producer topic denial",
    method=="kafka.Fetch",                                          "F: Consumer fetch denial (sampled)",
    method IN ("kafka.CreateTopics","kafka.DeleteTopics"),          "L: Topic lifecycle",
    method IN ("kafka.CreateAcls","kafka.DeleteAcls"),              "X: ACL change",
    method IN ("kafka.AlterConfigs","kafka.IncrementalAlterConfigs"),"C: Config change",
    method=="mds.Authorize",                                        "M: MDS (SR/Connect/ksqlDB)",
    1==1,                                                           "O: Other")
| stats count AS denials, dc(principal) AS principals BY class
| eventstats sum(denials) AS total
| eval pct=round(denials*100/total,1)
| fields class denials principals pct | sort - denials
```

### 4.4 Reusable macro
```
[cc_authz_denials]
definition = index=confluent_audit sourcetype=confluent:auditlog \
  ( (type="io.confluent.kafka.server/authorization" data.authorizationInfo.granted=false) \
    OR (type="io.confluent.kafka.server/request" data.result.status=FAILURE) )
iseval = 0
```
Usage: `` `cc_authz_denials` | stats count BY ... ``

> There is **no `Describe`-noise filter** here, deliberately: CC audit logs do not emit
> `Describe`/`DescribeConfigs` denials at all, so there is nothing to suppress. If your
> dataset is flooded with `Describe`, you are looking at self-managed CP logs, not CC
> audit logs.

### 4.5 Phantom-topic detection
`resourceName` is what the client *asked for*, not proof it exists. A typo yields a
denial, not "unknown topic." Maintain a `confluent_topic_inventory` lookup:

```spl
index=confluent_audit sourcetype=confluent:auditlog
  type="io.confluent.kafka.server/request" data.result.status=FAILURE
  data.methodName="kafka.Produce"
| rename data.authorizationInfo.resourceName AS resource_crn,
         data.authenticationInfo.principal   AS principal
| rex field=resource_crn "topic=(?<topic_name>[^/]+)$"
| lookup confluent_topic_inventory topic_name OUTPUT owning_app
| eval verdict=if(isnull(owning_app), "PHANTOM - topic does not exist", "Real topic - grant gap")
| stats count BY principal, topic_name, verdict | sort - count
```
(`resourceName` is a CRN — extract the topic segment before matching the inventory.)

---

## 5. Retention

`confluent-audit-log-events` retains **7 days** on the independent audit cluster; records
cannot be modified, deleted, or produced to directly. **7 days is the replay horizon** —
anything older exists only if Splunk already ingested it. Set Splunk index retention to
the compliance requirement (typically far longer), in coordination with security, and
**monitor sink lag**: a lagging sink past 7 days is permanent audit loss.

---

## 6. Remediation classes (audit-visible only)

Only classes the audit log can *show* live here. Consumer-group, metadata, and
below-broker classes are in the companion runbook.

### P — Producer topic denial
- **Signal:** `request` `kafka.Produce` FAILURE, `TOPIC_AUTHORIZATION_FAILED`, correct topic named.
- **Cause:** topic created outside the principal's granted prefix, or app holds only literal per-topic ACLs and a new topic was added.
- **Fix:** migrate to a **prefixed** grant rather than adding another literal ACL (§7).
- **Note:** idempotence needs only `WRITE` on the topic. `IdempotentWrite` was
  **deprecated in Kafka 2.8 (KIP-679)** and is not required on CC — do **not** grant a
  cluster-level `IdempotentWrite`. (The prior runbook's "Class A" is obsolete.)

### F — Consumer fetch (topic) denial
- **Signal:** `request` `kafka.Fetch` FAILURE — remember first-fetch-per-connection sampling.
- **Cause:** `Read` missing on the **Topic**. (The matching **Group** `Read`, also
  required, is *not* audit-visible — companion runbook.)
- **Fix:** grant `Topic:Read` on the prefix; always pair with `Group:Read`. Treat
  `Topic:Read` without `Group:Read` as a configuration defect.

### L / X / C — Lifecycle, ACL, config denials
- **Signal:** `authorization` `granted=false` on `CreateTopics`/`DeleteTopics`,
  `CreateAcls`/`DeleteAcls`, `AlterConfigs`.
- **Value:** these are the **change-control and privilege-escalation** signals — the
  strongest reason to keep this pipeline. An app principal denied a `CreateAcls` or
  `AlterConfigs` is doing something it should not.
- **Fix:** these are usually *correct* denials. Investigate, don't grant.

### M — MDS (Schema Registry / Connect / ksqlDB)
- **Signal:** `authorization` `granted=false`, `methodName="mds.Authorize"`.
- **Cause:** subject-level SR denial, Connect/ksqlDB RBAC gap.
- **Fix:** grant the SR subject / MDS role for the app namespace.

---

## 7. Structural remediation (unchanged — this is the durable fix)

Individual grants close tickets; namespace prefixes remove recurrence. Adopt prefixed
grants per application namespace. **Topic names follow canon
`{domain}.{application}.{version}.{entity}`** (e.g. `payments.fraud.v1.alerts` — version
is the *third* segment, not last), so a domain prefix is RBAC-clean:

```
Topic:PREFIXED   "payments.fraud."          -> Read, Write, Describe
Group:PREFIXED   "payments.fraud."          -> Read
Topic:PREFIXED   "payments.fraud.streams-"  -> Create, Read, Write, Delete   # Streams internals
Cluster                                     -> Describe                       # NOT IdempotentWrite
```

A new topic inside an existing namespace then needs no ACL change, no ticket, and
produces no denial — which *restores meaning* to the audit log: a denial becomes a
genuine signal that something crossed an ownership boundary.

**Do not loosen to reduce volume:**
- **Cluster `Create`** — defeats topic-naming governance, spawns unowned shadow topics
  that never match SR subjects. If auto-creation denies, set
  `allow.auto.create.topics=false` on the client instead.
- **Cluster `Alter` / `AlterConfigs` / `ClusterAction`** — administrative, not app, ops.
- **`Topic:*` wildcards** — prefix per data domain instead, even at the cost of more bindings.

**Check DENY first.** A DENY overrides any ALLOW regardless of specificity; a legacy
wildcard DENY keeps producing denials no matter how many roles you bind:
```
confluent kafka acl list --cluster <lkc> | grep DENY
```

**Move grants to GitOps** — Terraform against the Confluent provider, with a published
role matrix (produce / consume / run-Streams). If every ACL change needs a human on the
platform team, that team owns triage forever, dashboards notwithstanding.

**FSI overlay:** mTLS + RBAC, never username/password. Service account per application.
Audit log enabled on all production clusters. (Confluent Canon.)

---

## 8. Proactive alerts

### 8.1 New-principal denial (highest signal/noise)
A principal not denied in the trailing 30 days suddenly failing ⇒ wrong key in a deploy,
or an ungranted new workload.

```spl
`cc_authz_denials` earliest=-1h
| rename data.authenticationInfo.principal AS principal
| stats count AS denials BY principal
| search NOT [ search `cc_authz_denials` earliest=-30d@d latest=-1h
               | rename data.authenticationInfo.principal AS principal
               | stats count BY principal | fields principal ]
| where denials > 5
```
Schedule 15 min / window `-1h`. Severity High → platform on-call + owning app team.

### 8.2 Denial-rate spike per principal
```spl
`cc_authz_denials` earliest=-24h
| rename data.authenticationInfo.principal AS principal
| bin _time span=5m
| stats count AS denials BY _time, principal
| eventstats avg(denials) AS baseline, stdev(denials) AS sd BY principal
| eval sd=if(sd<1,1,sd), zscore=round((denials-baseline)/sd,2)
| where _time >= relative_time(now(),"-15m") AND denials >= 50 AND zscore > 3
| table _time principal denials baseline zscore | sort - zscore
```
Schedule 5 min. Medium, →High if sustained > 3 intervals.

### 8.3 Authentication-failure clustering (most reliable — `kafka.Authentication` is confirmed)
```spl
index=confluent_audit sourcetype=confluent:auditlog
  type="io.confluent.kafka.server/authentication"
  data.authenticationInfo.result!="SUCCESS" earliest=-15m
| rename data.authenticationInfo.principal   AS principal,
         data.authenticationInfo.result      AS result,
         data.requestMetadata.client_address AS src_ip
| stats count AS failures, dc(src_ip) AS distinct_ips, values(result) AS results BY principal
| eval assessment=case(
    failures>100 AND distinct_ips>3,  "Fleet-wide bad credential - likely rotation failure",
    failures>100 AND distinct_ips<=3, "Single workload, expired/wrong key",
    1==1,                             "Low volume - monitor")
| where failures > 20 | sort - failures
```
Schedule 15 min. High when `distinct_ips>3`. Copy **security** when one source IP fails
against *many distinct principals* — that is credential probing, not misconfiguration.

---

## 9. Self-service handoff

Publish a Splunk dashboard filtered by principal prefix so each app team sees its own
denials. Seed each team a saved search scoped to its `sa-` naming convention. Because the
audit log **cannot** show group-join or metadata denials, the client-side reporting in
the companion runbook is not optional — it is the primary mechanism for the largest class
of "can't consume" tickets.

---

*Validated 2026-07-17 against `confluent-docs` (CC audit-logging: authorization/authentication
event methods, Kafka management event methods, audit-log schema, retention, access/consume) and
KIP-679. Field paths reflect the documented CloudEvents envelope; confirm against one live sample
before wiring alerts. Companion: `cc-client-side-authz-denial-triage.md`.*
