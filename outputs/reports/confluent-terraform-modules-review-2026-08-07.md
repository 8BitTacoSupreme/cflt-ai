# Review: confluent-terraform-modules — Gateway & YAML Schema Breakdown

**Date:** 2026-08-07
**Source files:** <modules-repo>/README.md, <modules-repo>/CLAUDE.md
**Scope:** YAML-driven Terraform module set for Confluent Cloud — specifically the Network/Gateway config surface (`pni`, `privatelink`, `privatelink_gateway`), cluster-type gating, and provider-version claims, cross-checked against Confluent's own documentation, and evaluated for reader-facing clarity.
**Claims extracted:** 12

## Claims (extraction anchor)

```yaml
claims:
  - id: "readme-1"
    source_file: "README.md"
    source_section: "Repository structure"
    category: architecture_choice
    text: "networking/ # (placeholder — networking modules coming soon)"
  - id: "readme-2"
    source_file: "README.md"
    source_section: "Development"
    category: config_value
    text: "All modules require Terraform >= 1.3.0 and Confluent provider ~> 2.47.0."
  - id: "readme-3"
    source_file: "README.md"
    source_section: "Network"
    category: behavior_assertion
    text: "type: pni works on both dedicated and enterprise."
  - id: "readme-4"
    source_file: "README.md"
    source_section: "Cluster type guide"
    category: architecture_choice
    text: "dedicated | Yes | Yes (VPC peering or PNI) | Requires cku"
  - id: "readme-5"
    source_file: "README.md"
    source_section: "Cluster type guide"
    category: behavior_assertion
    text: "the PNI integration (modules/networking/aws/pni) is implemented and verified working end-to-end for both cluster types [dedicated/enterprise]"
  - id: "readme-6"
    source_file: "README.md"
    source_section: "Concept / Config file reference"
    category: config_value
    text: "networking/pni.yaml # one file = one private network (pni or privatelink)"
  - id: "readme-7"
    source_file: "README.md"
    source_section: "Environment"
    category: behavior_assertion
    text: "schema_context: \"\" — schema contexts are a Confluent Platform feature and are not supported in Confluent Cloud Schema Registry."
  - id: "readme-8"
    source_file: "README.md"
    source_section: "Cluster type guide (PrivateLink callout)"
    category: config_value
    text: "Requires provider confluent >= 2.60.0 — aws_ingress_private_link_gateway doesn't exist on earlier versions."
  - id: "readme-9"
    source_file: "README.md"
    source_section: "Network (privatelink_gateway block)"
    category: behavior_assertion
    text: "privatelink_gateway ... no aws_account_id needed, this model has no account-whitelist step at all."
  - id: "readme-10"
    source_file: "README.md"
    source_section: "Network (DNS callout)"
    category: comparison
    text: "privatelink and privatelink_gateway always provision their own Route53 zone/records automatically; pni only does so when use_aws_networking: true."
  - id: "readme-11"
    source_file: "README.md"
    source_section: "Cluster type guide"
    category: metric_sla
    text: "freight | Yes [RBAC] | Yes [private networking] | High-throughput workloads"
  - id: "claude-1"
    source_file: "CLAUDE.md"
    source_section: "PrivateLink — two different resource models, not one"
    category: architecture_choice
    text: "Keep PNI/PrivateLink (enterprise/dedicated) and purely-public (standard/basic) clusters in separate Confluent environments when both exist."
```

## Summary

The `privatelink`/`privatelink_gateway` split itself is accurate and well-evidenced against Confluent's Terraform provider schema and docs — that part of this session's work holds up. But the review surfaced a real, structural problem one layer up: **this repo's documentation has told readers for a while that PNI works on Dedicated clusters, and it doesn't** — Confluent's own AWS Private Network Feature Support matrix (and this project's own wiki) show PNI is Enterprise/Freight-only. That claim appears in three places (README's Network section, its Cluster type guide table, and its "verified working end-to-end" callout), and unlike the two PrivateLink paths, **PNI has no plan-time guard catching a Dedicated cluster that tries to use it** — meaning a reader following this repo's own docs today can walk straight into an unguarded, unsupported combination. A second, smaller issue: the provider-version bump made earlier this session (`~> 2.47.0` → `~> 2.60.0`) landed correctly in every `.tf` file but was missed in one prose sentence in the README, so the two files now disagree with each other. Recommendations below address both, plus the usability gap the prompt asked about directly: nothing in this repo currently helps a reader choose between the three networking options based on the trade-offs (eCKU ceiling, BYOK/Access Transparency availability) that actually differ between them.

## Claim Validation

### Repository structure & versioning

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| readme-1 | `networking/` listed as "placeholder — coming soon" | — | — (internal consistency check, not a doc lookup) | — | — | **Corrected** |
| readme-2 | Provider pin `~> 2.47.0` | — | `terraform-provider-confluent` CHANGELOG.md (fetched this session) | — | — | **Corrected** |
| readme-6 | Tree diagrams list only `pni or privatelink` | — | — (internal consistency check) | — | — | **Corrected** |
| claude-1 | "PNI/PrivateLink (enterprise/dedicated)" grouping | `wiki/concepts/network-connectivity-by-tier.md` | `docs.confluent.io/cloud/current/networking/overview.md` | — | — | **Corrected** (imprecise phrasing, contributes to readme-3/4/5's error) |

**Corrections:**
- **#readme-1:** `modules/networking/` contains three fully implemented, validated modules (`pni`, `privatelink`, `privatelink_gateway`) — none of this is a placeholder. This line predates the PrivateLink work and was never updated; it actively misleads a new reader skimming the repo layout before reading further. Fix: replace with the real subtree (`networking/aws/{pni,privatelink,privatelink_gateway}`).
- **#readme-2:** The provider pin was bumped to `~> 2.60.0` across every `versions.tf` and both example `providers.tf` this session (confirmed via `grep -rn "~> 2.6" --include="*.tf"` — 10/10 files consistent). This one sentence in the Development section is the sole holdout still saying `~> 2.47.0`, directly contradicting `terraform init`'s actual behavior and CLAUDE.md's own account of the bump.
- **#readme-6:** The Concept and Config-file-reference tree diagrams (two separate spots) say "one file = one private network (pni or privatelink)" — both predate `privatelink_gateway` and now disagree with the fully-updated Network section eight lines below them. Minor on its own, but it's exactly the kind of first-impression inconsistency a reader hits before reaching the section that actually explains the distinction.
- **#claude-1:** Not a factual error on its own — the sentence is about environment segregation, not a networking-support claim — but pairing "PNI/PrivateLink" and "(enterprise/dedicated)" as if either backs either reinforces the same wrong mental model corrected below (readme-3/4/5). Worth rewording once those are fixed, so this note doesn't silently keep the misconception alive after the primary claims are corrected.

### Network / Gateway cluster-tier gating

| # | Claim | Wiki | MCP | Skill | Skill Verdict | Verdict |
|---|-------|------|-----|-------|---------------|---------|
| readme-3 | "`type: pni` works on both `dedicated` and `enterprise`" | `wiki/concepts/network-connectivity-by-tier.md` | `docs.confluent.io/cloud/current/networking/overview.md` (AWS Private Network Feature Support table, fetched this session) | — | — | **Corrected** |
| readme-4 | Dedicated: "Yes (VPC peering or PNI)" | same as above | same as above | — | — | **Corrected** |
| readme-5 | "PNI integration... verified working end-to-end for both cluster types" | same as above | same as above | — | — | **Corrected** |
| readme-8 | Requires provider `>= 2.60.0` for `aws_ingress_private_link_gateway` | — | `terraform-provider-confluent` CHANGELOG.md + `terraform providers schema -json` (both fetched/run this session) | — | — | **Confirmed** |
| readme-9 | `privatelink_gateway` has no account-whitelist step | — | `registry.terraform.io/.../confluent_gateway` + `confluent_access_point` resource schemas (fetched this session) | — | — | **Confirmed** |
| readme-10 | DNS automation split (privatelink/privatelink_gateway auto; pni opt-in) | — | `docs.confluent.io/cloud/current/networking/aws-platt.md` + `aws-privatelink.md` (fetched this session) | — | — | **Confirmed** |
| readme-11 | Freight: RBAC Yes | — | `docs.confluent.io/cloud/current/clusters/cluster-types.md` (fetched this session) | — | — | **Confirmed** |

**Corrections:**
- **#readme-3 / #readme-4 / #readme-5 — the same underlying error, stated three times.** Confluent's own AWS Private Network Feature Support matrix lists Private Network Interface support for **Enterprise** and **Freight** clusters only — the Dedicated row has no checkmark in that column at all (Dedicated instead gets VPC Peering, Transit Gateway, and PrivateLink-Dedicated). This project's own `wiki/concepts/network-connectivity-by-tier.md` independently confirms the same thing: its connectivity table lists PNI under "Enterprise, Freight (AWS only)" and explicitly excludes Dedicated. So this isn't a close call needing interpretation — two independent sources (fetched fresh this session and pre-existing in this knowledge base) agree, and the repo's docs disagree with both.
  - Practical consequence: `modules/networking/aws/pni` has **no cluster-tier guard at all** (unlike the two PrivateLink modules, which this session added `_validate_privatelink_cluster_type`/`_validate_privatelink_gateway_cluster_type` preconditions for specifically because the wrong-tier case used to fail opaquely at Confluent's API). A reader who reads "PNI works on both dedicated and enterprise," sets `cluster_type: dedicated` + `network: { type: pni }`, and runs `terraform apply` gets no `plan`-time warning — they hit whatever error Confluent's API actually returns for that combination, live, the same class of problem this session just fixed for PrivateLink.
  - Also worth checking directly: every real example in this repo (`<env>/clusters/enterprise.yaml`) uses PNI with `cluster_type: enterprise`, never `dedicated` — nothing in the repo's own test coverage actually exercises the "verified... for both cluster types" claim for Dedicated. The claim reads as an assumption stated as a verified fact.
  - Fix: correct all three locations to say PNI is Enterprise/Freight-only; Dedicated's private-networking options are VPC Peering, Transit Gateway, or `privatelink` (Dedicated PrivateLink) — never PNI. Then decide whether to add the same kind of `plan`-time guard PrivateLink just got, so this doesn't repeat the exact failure mode this session already fixed once.
- **#readme-8 / #readme-9 / #readme-10 / #readme-11 confirmed as stated** — no changes needed on these.

### Gaps checked, unresolved

| # | Claim | Wiki | MCP | Verdict |
|---|-------|------|-----|---------|
| readme-7 | "Schema contexts... not supported in Confluent Cloud Schema Registry" | no matching article | `docs.confluent.io/cloud/current/stream-governance/schema-contexts.md` returned a redirect/404 this session — could not locate the current doc at that path | **Unverifiable** |

## Premise Challenge

| # | Premise | Assumption | Challenge | Severity |
|---|---------|------------|-----------|----------|
| 1 | A reader of the README's prose alone can correctly pick between `pni` / `privatelink` / `privatelink_gateway` for their cluster tier. | The three options are documented clearly enough, in one place, to self-serve the right choice. | There's no decision table or flowchart — just three parallel schema blocks. Worse, per readme-3/4/5, the guidance that *does* exist for one of the three (PNI) is itself wrong. A reader following this doc as written today could configure an unsupported combination the repo won't catch. | **Critical** |
| 2 | The provider-version constraint is uniform and matches what `terraform init` will actually resolve. | Every place the version is mentioned agrees. | It doesn't — `versions.tf` (10/10 files) says `~> 2.60.0`; README's Development section still says `~> 2.47.0`. A reader copying that line into their own tooling or CI pin would diverge from what this repo's own modules actually require. | Moderate |
| 3 | The three private-networking options are freely interchangeable alternatives, chosen by preference. | Cost/throughput/feature trade-offs between them either don't exist or don't matter for this repo's audience. | They're not interchangeable at all, on axes this repo never surfaces: per `cluster-types.md`, Enterprise clusters on **PrivateLink** are capped at 10 eCKU, while Enterprise on **PNI** unlocks 32 eCKU — a reader optimizing purely for "which is simpler to set up" could end up on the option with a 3x lower throughput ceiling without ever being told the ceiling differs. | **Critical** (directly undercuts the "easier to use" ask) |
| 4 | PNI is the lower-risk option of the three, so it doesn't need the same plan-time guard the two PrivateLink modules just got. | Guard coverage roughly tracks actual risk. | The opposite looks true right now: PNI is the one path with **both** an active documentation error (readme-3/4/5) **and** no guard — the exact failure mode (wrong tier, opaque API rejection) that motivated adding guards to `privatelink`/`privatelink_gateway` this session is currently *more* exposed on PNI, not less. | **Critical** |
| 5 | The choice between PNI and PrivateLink has no bearing on this project's FSI posture. | Regulated-environment requirements are indifferent to which private-networking model is used. | Per `cluster-types.md`'s feature comparison table, **self-managed encryption keys (BYOK)** and **Access Transparency** are Dedicated/Enterprise-tier features gated independently of the networking choice, but PrivateLink-Dedicated and PNI-Enterprise land on different cluster tiers with different feature ceilings — an FSI adopter choosing based on this repo's docs alone has no way to know that. Canon calls for exactly this kind of security-posture trade-off to be surfaced explicitly. | Moderate |

## Canon Compliance

| Area | Status | Notes |
|------|--------|-------|
| Security posture (mTLS + RBAC in regulated environments) | Partial | RBAC-vs-ACL gating by cluster tier is correctly documented and enforced (`CLAUDE.md`'s "Enterprise/dedicated vs standard/basic" section); mTLS/client-auth configuration for the Kafka cluster itself isn't addressed anywhere in this repo — out of scope for a cluster/topic/IAM provisioning tool, but worth a one-line pointer for FSI users. |
| Schema Registry governance | Compliant | The Topic YAML example uses AVRO with `FULL_TRANSITIVE` compatibility — matches canon's "Avro/Protobuf in production" default directly. |
| Naming convention (`<domain>.<entity>.<event>`) | Partial | Example topics (`payments.created`, `datagen.users`) follow a `domain.event`-shaped pattern but skip the `entity` segment canon specifies — minor, and it's example data rather than an enforced convention in the module itself. |
| Service accounts per application, not per team | Compliant | `modules/iam`'s one-SA-per-named-principal pattern (`admin`, `consumer-payments`, `datagen`) matches canon directly, and CLAUDE.md's "Design philosophy to preserve" section explicitly rules out implicit/shared-grant shortcuts. |
| Audit logging on production clusters | Gap | `cluster-types.md` confirms Audit Logs as a feature on Standard/Enterprise/Dedicated/Freight (not Basic) — this repo doesn't reference enabling or verifying it anywhere. |
| Private connectivity for prod (FSI default) | Partial (see Premise Challenge #5) | PNI/PrivateLink both satisfy "no public endpoint," but the repo doesn't surface the BYOK/Access Transparency feature-ceiling difference between the tiers each model is gated to. |

## Gaps

- **readme-7** (schema contexts / Confluent Cloud Schema Registry support) — could not verify via MCP this session; the referenced doc path redirected. Queued below rather than asserted either way.
- Whether `modules/networking/aws/pni` *should* get the same `_validate_*_cluster_type` precondition treatment as the two PrivateLink modules is a design decision, not something MCP/wiki can settle — flagged as a Recommendation instead.

**Auto-stub queued** (`wiki/_queue.md`, no existing coverage found):
```
- [ ] <!-- auto-stub: confluent-cloud-schema-registry-contexts --> wiki/concepts/confluent-cloud-schema-registry-contexts.md — Auto-queued from /review
      Claim: "Schema contexts are a Confluent Platform feature and are not supported in Confluent Cloud Schema Registry" | Date: 2026-08-07 | Source: confluent-terraform-modules/README.md
```

## Recommendations

1. **Fix readme-3/4/5 first — this is the one factual error, and it's the highest-severity finding.** Correct the Network section, the Cluster type guide table, and the "verified... for both cluster types" callout to state PNI is Enterprise/Freight-only. Then decide: add a `_validate_pni_cluster_type`-style precondition to `modules/clusters` (matching the pattern already used for both PrivateLink types), so a reader who still gets this wrong from some other source (a colleague, an old doc version, a memory) fails at `plan` with a clear message instead of an opaque Confluent API error.
2. **Reconcile the provider-version mention** (README's Development section → `~> 2.60.0`) so it matches every `.tf` file and CLAUDE.md's own account of the bump.
3. **Update the two stale tree diagrams and the "placeholder" line** so a reader's first read of the repo layout matches what's actually there.
4. **Add a short decision table for picking a networking model**, addressing the usability ask directly — something in the shape of:

   | Cluster tier | Options | Pick PNI if... | Pick PrivateLink if... |
   |---|---|---|---|
   | Enterprise | `pni` or `privatelink_gateway` | You need >10 eCKU (up to 32) or highest throughput at lowest cost | You want the simplest AWS-side setup and ≤10 eCKU is enough |
   | Dedicated | `privatelink` only | — (PNI isn't available on Dedicated) | Always, for private connectivity on Dedicated |

   This turns three parallel schema blocks into an actual decision aid — the specific gap Premise Challenge #1 and #3 identify.
5. **Surface the BYOK/Access Transparency trade-off** (Premise Challenge #5) somewhere near the cluster-type guide, even as a one-line pointer to `cluster-types.md`'s feature comparison table — relevant enough for this project's FSI-oriented audience to be worth the single sentence.

---
Canon stack: base + industry/fsi | Hash: 437a88b8eb364e19 | MANIFEST: unavailable (raw/repos/fsi-dsp/ is empty in this checkout) | Floor: claude-sonnet-5 | Generated: 2026-08-07T00:00:00Z
