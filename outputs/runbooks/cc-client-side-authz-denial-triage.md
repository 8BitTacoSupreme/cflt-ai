---
title: Client-Side Kafka Authorization Denial Triage
subtitle: Diagnosing the denials Confluent Cloud audit logs do not record
audience: Application teams (self-service), Platform / C4E (escalation)
validated: 2026-07-17 against confluent-docs (CC audit-logging coverage) + KIP-679 + Kafka client exceptions
confidence: high
companion: cc-audit-log-authz-triage-splunk.md
---

# Client-Side Kafka Authorization Denial Triage

**Purpose:** Diagnose and resolve the Kafka authorization failures that **do not appear
in Confluent Cloud audit logs** — consumer-group joins, metadata discovery, and
everything below the broker — from the client's own signals. This is the other half of
the audit-log runbook, and for most "can't consume" tickets it is the *primary* tool.

---

## 1. Why this runbook exists

CC audit logs record broker-side decisions for an enumerated set of request methods. The
following are **not** in that set, so they are invisible in Splunk and must be diagnosed
client-side:

| Failure | In audit log? | Client-side signal |
|---|---|---|
| Consumer **group** denial — `GROUP_AUTHORIZATION_FAILED` at `JoinGroup` | **No** (`JoinGroup`/`SyncGroup` not audited) | `GroupAuthorizationException` |
| `Describe` / `DescribeConfigs` metadata denial | **No** (not an audited method) | usually silent; metadata timeouts |
| Offset commit/fetch denial | **No** (`OffsetFetch`/`OffsetCommit` not audited) | `TopicAuthorizationException` / commit failures |
| Network / TLS / PrivateLink / DNS failure | **No** (below the broker) | connection timeouts, `NetworkClient` retries |
| Expired / wrong API key delivered by secrets manager | **Partially** (auth event exists, but the *cause* is client-side) | `AuthenticationException`, `SaslAuthenticationException` |

> **Producer/consumer *topic* denials are the exception** — those *are* audit-visible
> (as `request` FAILUREs; see companion runbook §4.2). Everything above is not. If a
> ticket's failure appears in neither this list's client signals nor the audit log, it is
> almost certainly **network/DNS/credential-delivery** — route below the broker.

---

## 2. Map the exception to the cause

Kafka client exceptions name the failure precisely — *if the application surfaces them*.

| Exception | Meaning | Missing grant / cause |
|---|---|---|
| `TopicAuthorizationException` → `unauthorizedTopics()` | Denied Read/Write on a topic | `Topic:Read` or `Topic:Write` on the named topic/prefix |
| `GroupAuthorizationException` → `groupId()` | Denied on the consumer group | **`Group:Read`** on the group ID (see §3 — the #1 "works in dev") |
| `ClusterAuthorizationException` | Denied a cluster op | Usually a *correct* denial — app attempting admin op |
| `SaslAuthenticationException` / `AuthenticationException` | Credential rejected | Expired/rotated/wrong key — **not** an ACL problem (§5) |
| `TimeoutException` with no authz exception | Never reached the broker | Network / DNS / PrivateLink / TLS — **not** platform-permissions |

The discriminator: **did an `*AuthorizationException` fire at all?** If yes → grant gap
(§3–4). If only `TimeoutException`/`AuthenticationException` → not a permissions problem.

---

## 3. Class B — Missing `Group:Read` on generated group IDs (the big one)

**Most common cause of "it works in dev," and invisible to the audit log.**

- **Symptom:** consumer authenticates, reads topic metadata, then fails at `JoinGroup`
  with `GROUP_AUTHORIZATION_FAILED`. Nothing in Splunk.
- **Cause:** frameworks generate group IDs the app team never reported:
  - Spring Kafka — defaults derived from `spring.application.name` or a random id
  - Kafka Streams — the group **is** `application.id`
  - Kafka Connect — `connect-<connector-name>`
  - ksqlDB — `_confluent-ksql-<service-id>`
- **Fix — do not chase literal group IDs.** Grant `Read` on a **`PREFIXED`** group
  pattern matching the app namespace:
  ```
  Group:PREFIXED  "payments.fraud."   -> Read
  ```
- **Pairing rule:** a consumer needs **both** `Topic:Read` *and* `Group:Read`. The topic
  half is audit-visible (companion §4.2 / class F); the group half is not. Treat
  `Topic:Read` without matching `Group:Read` as a configuration defect — it produces a
  consumer that connects, fetches metadata, then hangs at join with no Splunk trace.

---

## 4. Class C — Metadata discovery (`Describe`) denials

- **Symptom:** usually none visible to the app; occasional metadata-refresh timeouts.
  **Not** in the audit log — CC does not emit `Describe`/`DescribeConfigs` denials.
- **Cause:** clients call `Metadata`/`DescribeCluster` on every bootstrap and refresh.
  Under RBAC, a role bound to a topic prefix can still be denied `Describe` on topics
  discovered outside that prefix.
- **Fix:** grant cluster-level `Describe` to all app principals — it exposes nothing
  beyond cluster identity. Because these denials are not audited, there is **no residual
  volume to filter** (unlike self-managed CP); the fix is purely functional.

---

## 5. Class G — Authentication failure misread as authorization failure

- **Symptom:** user reports "not authorized," but no topic/group denial matches in Splunk
  and no `*AuthorizationException` in client logs.
- **Cause:** expired/rotated API key, wrong key injected by the secrets manager, or a
  network failure before the broker.
- **Fix:** check `authentication` events (companion §8.3). If the failure is there, it is
  credential delivery — fix the secret, not the ACLs. If it is in *neither* place, it is
  below the broker → route to **network**, not platform-permissions.
- **Idempotence note:** a producer that fails at startup with `TOPIC_AUTHORIZATION_FAILED`
  needs `WRITE` on the topic — **not** a cluster `IdempotentWrite`, which was deprecated
  in **Kafka 2.8 (KIP-679)** and does not exist on CC. If someone "fixed" a producer by
  granting cluster `IdempotentWrite`, remove it.

---

## 6. Kafka Streams internal-topic bursts

- **Symptom:** Streams app fails at startup with a burst of `Create`/`Write` denials
  against topics the team does not recognize — looks alarmingly like a security event.
  (The `Create` denials *are* audit-visible as `authorization` events; the `Write` path
  is a `request` FAILURE.)
- **Cause:** Streams creates changelog/repartition topics named `<application.id>-*`,
  rarely in the original access request.
- **Fix:**
  ```
  Topic:PREFIXED  "<application.id>-"  -> Create, Read, Write, Delete
  ```

---

## 7. Fix the upstream cause: client observability

The measurement above only helps if the client *surfaces* the exception. When app teams
"cannot report the topic and operation," the defect is in their code, not the platform:

- `catch (Exception e) { log.error("kafka error"); }` swallowing
  `TopicAuthorizationException` and its `unauthorizedTopics()` set — **log the set**.
- Retry loops masking the first failure until the client merely *appears* hung — log the
  first authz exception before backoff.
- `org.apache.kafka.clients.NetworkClient` and `...Metadata` not at `DEBUG` — the two
  loggers that distinguish "denied" from "never connected."
- No visibility into **which API key** the running process actually loaded — log the key
  id (`sa-xxxxx`), never the secret.

**Minimal consumer diagnostic (log the exact grant gap):**
```java
try {
    consumer.poll(Duration.ofSeconds(5));
} catch (TopicAuthorizationException e) {
    log.error("Denied Read on topics={} — need Topic:Read on the prefix", e.unauthorizedTopics());
} catch (GroupAuthorizationException e) {
    log.error("Denied on group={} — need Group:Read on the prefix", e.groupId());
}
```

---

## 8. Self-service handoff (the payoff)

**Require in every access ticket** — this resolves the majority without anyone reading a log:
- The exception class (`TopicAuthorizationException` / `GroupAuthorizationException` / …)
- Contents of `unauthorizedTopics()` and/or the `groupId()`
- The consumer group ID (the real one the framework generated)
- The API key prefix (`sa-xxxxx`) — **never** the secret

**Publish a role matrix** ("what do I need to produce / consume / run Streams") so app
teams self-serve the grant, and move grants to **GitOps** (Terraform + Confluent
provider). If every ACL change needs a platform human, that team owns triage forever.

**Grant pattern (canon-aligned, `{domain}.{application}.{version}.{entity}` naming):**
```
Topic:PREFIXED   "payments.fraud."          -> Read, Write, Describe
Group:PREFIXED   "payments.fraud."          -> Read
Topic:PREFIXED   "payments.fraud.streams-"  -> Create, Read, Write, Delete
Cluster                                     -> Describe
```

**FSI overlay:** mTLS + RBAC, never username/password; service account per application.

---

## 9. Decision flow

```
"can't produce/consume"
   |
   ├─ *AuthorizationException in client logs?
   |     ├─ TopicAuthorizationException  → grant Topic:Read/Write on prefix   (also audit-visible: companion §4.2)
   |     ├─ GroupAuthorizationException  → grant Group:Read on prefix         (§3 — NOT in audit log)
   |     └─ ClusterAuthorizationException→ likely a correct denial; investigate
   |
   ├─ AuthenticationException / SaslAuthenticationException?
   |     → credential delivery: check auth events (companion §8.3), fix the secret
   |
   └─ Only TimeoutException, nothing in audit log, nothing in client authz logs?
         → below the broker: network / DNS / PrivateLink / TLS  → route to network
```

---

*Validated 2026-07-17 against `confluent-docs` (CC audit-logging coverage — `JoinGroup`,
`Describe`, offset methods confirmed absent from audited methods), KIP-679, and Kafka client
exception semantics. Companion: `cc-audit-log-authz-triage-splunk.md`.*
