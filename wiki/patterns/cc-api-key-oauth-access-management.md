---
title: Confluent Cloud Access Management — API Keys vs OAuth (PingFederate) for FSI
tags: [confluent-cloud security oauth oidc identity-pools api-keys rbac pingfederate service-accounts multi-org terraform github-actions fsi compliance]
sources:
  - https://docs.confluent.io/cloud/current/security/authenticate/workload-identities/identity-providers/oauth/overview.html
  - https://docs.confluent.io/cloud/current/security/authenticate/workload-identities/identity-providers/oauth/best-practices.html
  - https://docs.confluent.io/cloud/current/security/authenticate/workload-identities/identity-providers/oauth/identity-providers.html
  - https://docs.confluent.io/cloud/current/security/authenticate/workload-identities/service-accounts/api-keys/best-practices-api-keys.html
  - https://docs.confluent.io/cloud/current/security/authenticate/workload-identities/manage-workload-identities.html
  - https://docs.confluent.io/cloud/current/security/access-control/rbac/predefined-rbac-roles.html
  - https://docs.confluent.io/cloud/current/security/access-control/hierarchy/organizations/multiple-organizations.html
  - https://docs.confluent.io/cloud/current/quotas/service-quotas.html
  - https://registry.terraform.io/providers/confluentinc/confluent/latest
related: [patterns/terraform-cicd-confluent-private-networking, patterns/auditor-readonly-rbac-payload-isolation, patterns/audit-log-siem-integration, patterns/fsi-governance-automation, patterns/topic-naming]
confidence: medium
last_updated: 2026-10-01
last_validated: 2026-09-30
---

# Confluent Cloud Access Management — API Keys vs OAuth (PingFederate) for FSI

## Summary

For a strict-compliance FSI client on Confluent Cloud (CC), the target state is **OAuth/OIDC via the client's corporate IdP (e.g. PingFederate) mapped to identity pools for all workloads, with CC API keys reduced to a short, owned, expiring exception list**. OAuth replaces long-lived SASL/PLAIN secrets with short-lived JWTs, puts revocation in corporate IAM, and — with workload federation — leaves CI pipelines holding no stored secret at all. Because OAuth onboarding (IdP token config, JWKS allowlisting, token exchange) rarely lands by go-live, the practical rollout is **API keys under a strict baseline on day one, migrating app-by-app to OAuth**. Two CC facts drive the design: there are **no custom RBAC roles**, and with **one IdP across multiple CC orgs, a token is valid in every org** — only identity-pool filters separate dev from prod.

> **Confidence note:** all Confluent Cloud claims (roles, quotas, OAuth limits, Terraform provider OAuth support) were validated against `confluent-docs` and the Terraform registry on 2026-09-30. **PingFederate-side configuration** (JWT ATM, claim mapping, token exchange) is from practitioner knowledge and **must be validated by the client's Ping administrators** — that is why this article is `medium`.

## Pattern

### 1. Org and RBAC context this pattern assumes

- **Prod is its own CC org; Dev+QA share a non-prod org** (environments per stage). Confluent's default guidance is "environments and RBAC … instead of creating separate organizations", but an FSI prod boundary justifies the split. Constraints: **one annual commit applies to one org**, and **resources cannot be moved between orgs** — decide during onboarding.
- **OrganizationAdmin is break-glass only** (2 named SSO humans per org, no API keys). Adding an OAuth identity provider **requires OrganizationAdmin**, so IdP registration is a recorded break-glass change per org.
- Working roles: `EnvironmentAdmin` (platform team, per environment), `ResourceOwner` on prefixed topics/subjects (CI per domain), `DataSteward`/`Operator` (metadata, no data access), `AccountAdmin` (IAM automation — the only non-break-glass role with full identity-pool alter/delete).
- **Identity-pool creation cannot be fully prevented:** `ResourceOwner` on *any* resource, plus `EnvironmentAdmin`/`CloudClusterAdmin`, can create service accounts and identity pools. New identities can only be granted what the creator owns, so control is **audit-log detection + Terraform reconciliation**, not prevention.

### 2. Why API keys alone fall short for regulated workloads

| Control | CC API keys | OAuth + identity pools |
|---|---|---|
| Credential lifetime | Valid until deleted | Short-lived JWT; client re-auths automatically (KIP-368) |
| Secret location | Secret stores, CI vars, laptops — copies proliferate | With workload federation, no secret in the pipeline |
| Leaver / revocation | Manual CC key deletion, separate from corporate IAM | Disable the IdP client → access ends within token lifetime |
| Access review | Per-org key inventory | IdP app registrations, reviewed with everything else |
| Rotation evidence | Prove every key rotated | Nothing to rotate |
| Residual access | Docs warn API keys created under an admin role can **outlive the role binding** (documented for ksqlDB) | No persisted credential |

### 3. Target: OAuth-primary with PingFederate

**CC side (per org):** add PingFederate as **"Other OIDC identity provider"** (CC has no Ping-specific tab; the docs position this type for any OIDC-compliant provider). Supply the discovery URL `https://<pingfed-host>/.well-known/openid-configuration`, which auto-fills Issuer and JWKS URIs. The JWKS response must use `Content-Type` `application/json`, `application/jwk+json`, or `application/jwk-set+json`. The identity claim defaults to `claims.sub` and is what appears in audit logs.

**PingFederate side (validate with Ping admins):**

1. **JWT access tokens, not reference tokens.** CC accepts only JWT access tokens; configure a JSON Web Token Access Token Manager for Confluent clients.
2. **Explicit claim mapping** in the ATM attribute contract: `sub` (or `client_id`) = OAuth client ID; `aud` = CC-specific audience per org (e.g. `confluent-cloud-prod`); optional stage claim (`env`). Client-credentials tokens may not carry a useful `sub` by default.
3. **One OAuth client per application per stage**, `client_credentials` grant, **`private_key_jwt`** client auth preferred over client secrets (Kafka clients support client assertions natively — Java via `sasl.oauthbearer.assertion.*`, librdkafka via `sasl.oauthbearer.method=oidc` with the jwt-bearer grant).
4. **JWKS internet reachability.** CC fetches JWKS from its public IPs; on-prem PingFed behind a WAF must allowlist them. Confluent says to verify this **at least every three months** — a broken JWKS path fails every OAuth client.
5. **Signing-key rollover:** publish new keys in JWKS before signing with them; CC offers a manual JWKS refresh if timing slips.

**Pool filters — always pin audience and subject, per org:**

```text
# Prod org: pool for the payments producer
claims.aud == "confluent-cloud-prod" && claims.sub == "cc-prod-payments-producer"
```

Never `true`, never issuer-only. Confluent's best-practices page states pool IDs are **not sensitive** — filters are the only control.

**Runtime clients:** `SASL/OAUTHBEARER`; minimum Apache Kafka client 3.2.1, librdkafka 1.9.2, CP 7.2.1. OAuth Kafka auth works on **Standard, Enterprise, Dedicated, Freight** only. For data-centre/mainframe apps with existing PKI, **mTLS certificate identity pools** are the equivalent no-shared-secret option.

### 4. CI/CD (GitHub Actions → Terraform) with no stored secret

The Confluent Terraform provider's `oauth {}` block is **GA**. Option 1 (client id/secret + token URL) supports token refresh; Option 2 (pre-fetched `oauth_external_access_token`) does **not** refresh, so the token must outlive the apply.

| Option | Flow | Trade-off |
|---|---|---|
| **A. PingFed token exchange (RFC 8693)** | Job's GitHub OIDC token → PingFed validates against GitHub JWKS (repo + `environment:prod`) → issues CC-audience JWT | Single corporate control point; requires a PingFed token-exchange policy — **confirm version/licensing** |
| **B. GitHub as a second CC OIDC provider (CI only)** | `token.actions.githubusercontent.com` registered in CC; pool filter on `repo`, `environment`, custom `aud` | No Ping build; CI identity lives outside corporate IdP |

Prefer **A**; use **B** for CI only if A can't land in time. Never fall back to a client secret in GitHub secrets.

```hcl
provider "confluent" {
  oauth {
    # Pre-fetched token from the token-exchange step; not refreshed by the provider,
    # so it must outlive the longest apply
    oauth_external_access_token = var.cc_oauth_token
    # Pool IDs are non-sensitive; the pool filter is the real control
    oauth_identity_pool_id = var.cc_prod_terraform_pool_id
  }
}

resource "confluent_identity_pool" "prod_terraform" {
  identity_provider { id = confluent_identity_provider.pingfed.id }
  display_name   = "pool-prod-terraform"
  identity_claim = "claims.sub"
  # Pin to one Ping client and one prod audience; never issuer-only
  filter = "claims.aud == \"confluent-cloud-prod\" && claims.sub == \"cc-prod-terraform\""
}
```

Gate the GitHub job on a protected `prod` environment with required reviewers, so approval happens **before** a credential is issued. Data-plane resources on private networking still need an in-VPC runner — see [Terraform CI/CD over Private Networking](terraform-cicd-confluent-private-networking.md).

### 5. Documented API-key exceptions (OAuth-primary model)

| Exception | Reason | Control |
|---|---|---|
| `confluent_catalog_integration`, `confluent_custom_connector_plugin`, `confluent_flink_artifact`, `confluent_tableflow_topic` | Terraform provider: not yet supported with OAuth | Separate state, dedicated SA, Vault-issued key |
| Fully managed connectors → Kafka | Connectors authenticate as service accounts | Prefer service-account assignment (`Assigner`) over embedded keys |
| Audit-log consumer | Org quota: **2 audit-log API keys** | SIEM integration only, rotated, alerted |
| Metrics API scraper without OAuth support | Tool limitation | `MetricsViewer` only, scoped per org |
| Break-glass | IdP/JWKS outage recovery | One per org, sealed Vault path, dual-control retrieval, alert on use |

Identity-pool **ACLs can be managed only via CLI/REST API** — use RBAC role bindings on pools so access stays in Terraform.

### 6. Baseline: API-key-only operating standard

Applies on day one and to every remaining exception key.

**Issuance**
- **Service-account keys only** outside dev. User-account keys are **deleted when the user is deleted**, breaking production apps.
- **One service account per application per stage**, never per team.
- **Resource-scoped keys by default.** **Global API keys** (one key across Cloud Management API, Kafka, SR, Flink, Tableflow, ksqlDB) exist, but Confluent advises against them for single-resource clients; quota **2 per service account**, and a global key counts once against each cluster's key quota it is used with.
- **Separate issuer from consumer:** a pipeline holding `ResourceKeyAdmin` issues keys (it cannot create keys for itself); app teams never mint their own.
- Keys go **straight into a secrets manager** — never displayed, never in Git/CI variables/Terraform outputs; encrypt and restrict Terraform state.

**Rotation**
- **≤ 90 days** (Confluent's stated guidance; FSI policies often require 30–60) and immediately on suspected compromise or holder role change.
- **Overlap rotation:** create new → roll apps → confirm the old key is idle in audit logs → delete → verify deletion.
- Apps read keys at runtime from the secrets manager so rotation needs no redeploy.
- **Quotas to plan around:** 100 keys per service account; 3,000 cloud API keys per org; per-cluster 50 (Basic) / 250 (Standard) / 2,500 (Enterprise, Freight) / 20,000 (Dedicated). Overlap rotation transiently doubles counts.

**Removal and review**
- Quarterly reconciliation: `confluent api-key list --service-account <sa-id>` vs the owned inventory; unowned → delete.
- Delete keys idle 30+ days (audit-log authentication events show usage).
- **Revoke runbook deletes keys** whenever a role binding is removed.
- Retire the service account with the app (its keys go with it).

**Detection** (audit logs → SIEM, per org): key creation by anyone but the issuing pipeline; use from unexpected source IPs; auth failures on a valid key ID; any break-glass use; any new `OrganizationAdmin` binding (CC also emails existing OrgAdmins); identity-pool creation outside the IAM automation SA. Add `confluent_ip_filter` on the management API so a stolen cloud key is useless outside corporate egress.

### 7. Rollout sequence

1. Stand up the org structure, break-glass OrgAdmins, and the API-key baseline (§6).
2. In the **non-prod org first** (Confluent recommends trialling OAuth outside production): register PingFed, build the JWT ATM + claim mapping, allowlist CC IPs to JWKS, create one pool per app.
3. Migrate CI to OAuth (token exchange or GitHub OIDC provider).
4. Migrate runtime apps app-by-app; delete each app's API keys after cutover.
5. Repeat in the Prod org with prod-specific Ping clients/audiences.
6. Freeze the residual API keys as the §5 exception register; review quarterly.

## When to Use

- FSI or other regulated clients onboarding to Confluent Cloud with audit requirements on credential lifetime, rotation evidence, and joiner/mover/leaver controls.
- Multi-org CC topologies (org per stage) sharing one corporate IdP.
- Clients standardised on PingFederate (or any non-Entra/Okta OIDC IdP) that need the "Other OIDC" integration path.
- Terraform/GitHub Actions pipelines that must not hold long-lived CC credentials.

## Caveats

- **One IdP, many orgs = tokens valid everywhere.** Missing `aud`/`sub` pins in a single permissive pool filter in any org is a cross-org privilege path.
- **JWKS reachability is a hard dependency.** On-prem PingFed + firewall changes can silently break all OAuth auth; schedule the quarterly check.
- **Terraform Option 2 tokens don't refresh** — long applies against short-lived IdP tokens fail mid-run. Check the IdP token lifetime; split large applies.
- **Four Terraform resources still need cloud API keys** (§5); re-check the provider docs on upgrade — this list shrinks over time.
- **Basic clusters:** no OAuth and no RBAC role bindings on Kafka resources — never use them for regulated workloads.
- **Unverified:** PingFed JWT ATM/claim-mapping specifics and RFC 8693 token-exchange availability in the client's Ping version; whether Metrics API and SR REST calls made *outside* Terraform accept OAuth tokens — confirm before retiring observability keys.
- **No custom roles in CC:** least privilege is achieved by scope (CRN pattern/prefix), not by trimming role permissions.

## Related

- [Terraform CI/CD over Private Networking](terraform-cicd-confluent-private-networking.md) — plane split, in-VPC runners, and the GitHub OIDC → identity pool baseline this extends
- [Audit Log → SIEM Integration](audit-log-siem-integration.md) — where the detection rules in §6 run
- [Auditor-Readonly RBAC Payload Isolation](auditor-readonly-rbac-payload-isolation.md) — read-only RBAC scoping without data access
- [FSI Governance Automation](fsi-governance-automation.md) — governance-as-code context for the Terraform modules
- [Topic Naming Convention](topic-naming.md) — prefixes that make `ResourceOwner`/`DeveloperRead` prefix bindings work
