---
title: Schema Linking CP → CC When CP Schema Registry Uses mTLS
tags: [schema-registry, schema-linking, mtls, oauth, confluent-cloud, confluent-platform, migration, hybrid, cluster-linking, security, fsi]
related: [concepts/schema-registry-best-practices, concepts/cluster-linking-topology, patterns/dr-cluster-linking, patterns/cp-mtls-self-signed-setup, patterns/cp-tls-debugging-by-component, synthesis/confluent-gotchas-top-20]
confidence: medium
last_updated: 2026-10-01
last_validated: 2026-10-01
---

# Schema Linking CP → CC When CP Schema Registry Uses mTLS

## Summary

Confluent Cloud Schema Registry does **not** accept mTLS. CC mTLS covers "Kafka clusters and Confluent Platform clusters" only, and CC SR authenticates with **API keys** or **OAuth/OIDC via identity pools**. That doesn't block a CP→CC schema migration or link. The **exporter runs inside the CP SR** and calls CC **outbound**, so the CP mTLS listener stays untouched and only the exporter's *CC-side* credential matters. mTLS only becomes a real blocker in the **reverse direction (CC → CP)**. There the CC-hosted exporter can't present a client cert, and CP SR must be reachable over the public internet. Recommended shape: CP-side exporter → CC SR context in IMPORT mode, authenticated with OAuth (or a scoped service-account API key as fallback), paired with Cluster Linking for the data.

## Pattern

### Architecture

```text
CP SR (READWRITE, mTLS for on-prem clients — unchanged)
   └── exporter (runs inside CP SR) ──HTTPS, outbound──► CC SR (destination context in IMPORT mode)
                                      CC credential: OAuth (preferred) or scoped API key
CP Kafka ──Cluster Link (mirror topics, schema IDs preserved)──► CC Kafka
```

Supported Schema Linking topologies (CP docs, `schema-linking-cp.html`):

| Source | Destination |
|---|---|
| CC (internet networking) | CC (internet networking) |
| CC (internet networking) | CP 7.0+ **with an IP reachable over the public internet** |
| CP 7.0+ | CP 7.0+ |
| CP 7.0+ | CC (internet networking) |

Private endpoints for SR can also be used when creating exporters on either side ("Schema Linking on private networks").

### Exporter configuration (CP side)

The exporter `--config-file` accepts any SR client configuration. That includes the `bearer.auth.*` OAuth keys documented in `sr-client-configs`.

```properties
schema.registry.url=https://psrc-xxxxx.<region>.<cloud>.confluent.cloud
# OAuth client-credentials against the corporate IdP, mapped to a CC identity pool.
# Keeps FSI "no static passwords" intact; tokens are short-lived.
bearer.auth.credentials.source=OAUTHBEARER
bearer.auth.issuer.endpoint.url=https://login.microsoftonline.com/<tenant>/oauth2/v2.0/token
bearer.auth.client.id=<exporter-app-client-id>
bearer.auth.client.secret=<from-vault>
bearer.auth.scope=<scope>
bearer.auth.logical.cluster=lsrc-xxxxx        # CC SR cluster ID
bearer.auth.identity.pool.id=pool-xxxxx
# Fallback (the documented CP→CC example): API key owned by a dedicated service account.
# basic.auth.credentials.source=USER_INFO
# basic.auth.user.info=<SR_API_KEY>:<SR_API_SECRET>
# Corporate egress proxy, if any (documented for CP→CC exporters):
# proxy.host=https://proxy.corp.example
# proxy.port=8443
```

> **Unverified:** the docs state the exporter config accepts any SR client config, but no page shows an OAuth identity-pool exporter targeting CC end to end. The documented CP→CC example uses `basic.auth` with an API key. Prove OAuth works in a sandbox (local CP SR with mTLS listener → sandbox CC env) before committing to it for a client.

### Workarounds, ranked

1. **CP-side exporter → CC with OAuth** (above). Best FSI fit because no long-lived secret is stored. Subject to the sandbox proof.
2. **Same exporter with a service-account API key.** The documented path. Store the secret in the vault, rotate it, and position it as a system-to-system credential, not a user password. Scope it to ResourceOwner on the destination context/subjects only.
3. **One-time migration script, run on-prem.** For a cutover (not ongoing sync), or where exporters can't be licensed. Put the CC target context in IMPORT mode. Read from CP with the mTLS client cert (`ssl.keystore.*`) and write to CC with OAuth or an API key, keeping the IDs. Register referenced schemas before their referrers.
4. **CC → CP for failback.** The CC exporter can't do mTLS, and CP must be publicly reachable. Options:
   - Add a second CP SR listener with basic/OAuth auth, restricted by IP allowlist to CC egress.
   - Run option 3 in reverse from on-prem.

   Prefer the script. CP stays mTLS-only with no inbound exposure.

### Steps

1. Create the CC identity: an OAuth identity pool, or a service account + API key, scoped to the target context.
2. Set the destination context (e.g. `.onprem`) to IMPORT. Using a context keeps the CC default context READWRITE for cloud-native subjects and avoids ID collisions.
3. Create the exporter on CP: `--context-type CUSTOM --context-name onprem` (or `AUTO`), with `--subjects` filtered to what's needed rather than `:*:`.
4. Check subject/version/ID parity between source and destination.
5. Start Cluster Link mirror topics. Mirrored records carry the source schema IDs, so consumers pointed at the linked context deserialize without change.
6. Cut over consumers, then producers. CC-bound clients switch from mTLS to `bearer.auth.*` OAuth, since mTLS isn't available for CC SR. Plan this per application; it isn't a URL swap.
7. Promote: set CC to READWRITE and CP to READONLY, then delete the exporter.

## When to Use

- Hybrid CP + CC estates where on-prem SR is mTLS-only and schemas must exist in CC (migration, DR to cloud, cloud analytics fan-out).
- FSI engagements where security teams reject "CC SR doesn't do mTLS" as a blocker. The answer is that mTLS stays on-prem and the cloud leg uses OAuth.

## Caveats

- **Licensing (CP 8.1+):** exporters require a Confluent Enterprise license **or** the Customer-Managed CP for CC subscription. The latter only permits a CC destination registry, which is fine for this pattern.
- **Exporters outlive their creator's access.** Revoking or deleting the creating principal does not stop a running exporter. Monitor SR REST access logs for POST/PUT/DELETE on `/exporters`.
- **Exporter quotas on CC:** 10 per environment on Essentials, 100 on Advanced.
- **Linking several sources to the same destination context** can cause schema ID conflicts. Use one context per source.
- **Bidirectional linking** only works if each direction targets a different context.
- **Network:** CP→CC is outbound-only. Use a CC SR private endpoint for private CC networking, or `proxy.host`/`proxy.port` behind an egress proxy.

## Related

- [Schema Registry Best Practices](../concepts/schema-registry-best-practices.md) — schema IDs not portable; Schema Linking as the CC↔CP answer
- [Cluster Linking Topology](../concepts/cluster-linking-topology.md) — data-plane half of the hybrid link
- [DR — Cluster Linking](dr-cluster-linking.md) — failover/failback flow that the SR mode flips (READWRITE/IMPORT) must track
- [Confluent Platform mTLS Setup with Self-Signed Certs](cp-mtls-self-signed-setup.md) — building the local mTLS SR rig for the sandbox proof
- [Confluent Platform TLS Debugging by Component](cp-tls-debugging-by-component.md) — SR REST vs kafkastore TLS debugging
