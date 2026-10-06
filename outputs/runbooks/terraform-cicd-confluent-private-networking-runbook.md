---
title: Terraform CI/CD for Confluent Cloud over Private Networking — Deployment & Operations Runbook
subtitle: GitHub Actions + self-hosted ARC runners in-VPC, two-plane Terraform, OIDC auth; third-party CDC agent landing zone
audience: Platform / C4E (owners), app teams (data-plane PRs), cloud networking (VPC + private DNS)
validated: 2026-07-29 against confluent-docs (Terraform provider resource inventory, two-tier auth, terraform-security identity-pool/OIDC + state guidance) + Terraform registry (confluentinc/confluent 2.80.0) + local canon (topic-naming, schema-registry-adoption-playbook, fsi-governance-automation). The management-vs-data-plane reachability split is provider mechanics (kafka/schema resources require the private rest_endpoint), reasoned not doc-cited.
confidence: high
companion: ../../wiki/patterns/terraform-cicd-confluent-private-networking.md
related-canon: patterns/terraform-cicd-confluent-private-networking.md, concepts/private-networking.md, patterns/schema-registry-adoption-playbook.md, patterns/topic-naming.md, patterns/fsi-governance-automation.md
---

# Terraform CI/CD for Confluent Cloud over Private Networking

**Purpose:** Stand up and operate GitHub Actions CI/CD for Terraform-managed Confluent Cloud
when the cluster is on private networking, and manage the **third-party CDC agent (e.g. Precisely) → Confluent Cloud CDC
landing zone** through it.

> **The constraint that drives everything.** Data-plane resources (`confluent_kafka_topic`,
> `confluent_kafka_acl`, `confluent_schema`, `confluent_flink_statement`) hit the cluster's
> **private** `rest_endpoint`/SR endpoint — unreachable from a GitHub-hosted runner. They
> must run on a **self-hosted runner inside the VPC**, and the code must be **split by plane**.
> See the [companion pattern](../../wiki/patterns/terraform-cicd-confluent-private-networking.md).

---

## 0. Prerequisites

- Confluent Cloud environment on **private networking** (PrivateLink / peering / PNI / TGW),
  with the cluster's private DNS zone known.
  - **If PrivateLink:** know your tier's model — Enterprise = ingress PrivateLink Gateway
    (`confluent_gateway` + `confluent_access_point`); Dedicated = `confluent_network` +
    `confluent_private_link_access`. PL endpoints are **per-AZ (≤10/gateway)** — the ARC node
    pool must span the AZs that have an endpoint. The endpoint's **security group must allow
    `tcp/443` inbound from the runner CIDR** — the most common cause of a private-IP-resolves-
    but-times-out failure (§7). See [Private Networking](../../wiki/concepts/private-networking.md).
- A **VPC (or peered CI subnet)** with the private path to Confluent Cloud — the same one
  the CDC agents use.
- **EKS cluster** (or ASG host pool) in that VPC to run **Actions Runner Controller (ARC)**.
- Cloud secrets manager (Vault / AWS Secrets Manager / GSM / Key Vault) for the cluster API key.
- Remote TF backend (S3+DynamoDB / GCS / azurerm), SSE-KMS encrypted, reachable via VPC endpoint.
- Confluent provider pinned to **2.80.0**.

---

## 1. Repo layout — two planes, two states

```
infra/
├── platform/            # MANAGEMENT plane — public api.confluent.cloud, any runner
│   ├── backend.tf       #   remote state: platform/terraform.tfstate
│   ├── network.tf       #   PL plane-A: confluent_gateway + confluent_access_point (Enterprise)
│   │                    #   or confluent_network + confluent_private_link_access (Dedicated)
│   ├── cluster.tf       #   confluent_kafka_cluster (+ prevent_destroy)
│   ├── identity.tf      #   confluent_identity_provider / _identity_pool (GitHub OIDC)
│   ├── accounts.tf      #   confluent_service_account, confluent_role_binding, confluent_api_key
│   └── outputs.tf       #   cluster id + rest_endpoint (consumed by data/)
└── data/                # DATA plane — private rest_endpoint, IN-VPC runner ONLY
    ├── backend.tf       #   remote state: data/terraform.tfstate
    ├── remote_state.tf  #   terraform_remote_state -> platform outputs
    ├── topics.tf        #   confluent_kafka_topic
    ├── schemas.tf       #   confluent_schema, confluent_subject_config
    ├── acls.tf          #   confluent_kafka_acl
    └── flink.tf         #   confluent_flink_statement (needs Flink provider block + principal, see §2)
```

---

## 2. Provider config

```terraform
terraform {
  required_providers {
    confluent = { source = "confluentinc/confluent", version = "2.80.0" }
  }
}

# platform/ — management plane. Reads CONFLUENT_CLOUD_API_KEY / _SECRET from env
# (populated from a short-lived OIDC-exchanged credential; see §4).
provider "confluent" {}

# data/ — data plane. Bind to the PRIVATE cluster endpoint + a cluster-scoped key.
provider "confluent" {
  kafka_id            = data.terraform_remote_state.platform.outputs.cluster_id
  kafka_rest_endpoint = data.terraform_remote_state.platform.outputs.cluster_rest_endpoint  # private
  kafka_api_key       = var.cluster_api_key       # from secrets manager, not a GH secret
  kafka_api_secret    = var.cluster_api_secret
  # Schema Registry (also private):
  schema_registry_id            = data.terraform_remote_state.platform.outputs.sr_id
  schema_registry_rest_endpoint = data.terraform_remote_state.platform.outputs.sr_rest_endpoint
  schema_registry_api_key       = var.sr_api_key
  schema_registry_api_secret    = var.sr_api_secret

  # Flink (also private under PrivateLink — same gateway as Kafka+SR). REQUIRED if the data
  # plane manages any confluent_flink_statement. Omitting flink_principal_id (or a per-resource
  # principal {} block) fails with "one of provider.flink principal id ... must be set".
  organization_id       = data.confluent_organization.main.id
  environment_id        = var.environment_id
  flink_compute_pool_id = data.terraform_remote_state.platform.outputs.flink_compute_pool_id
  flink_rest_endpoint   = data.terraform_remote_state.platform.outputs.flink_rest_endpoint  # private
  flink_api_key         = var.flink_api_key
  flink_api_secret      = var.flink_api_secret
  flink_principal_id    = var.flink_principal_id  # the SA statements run as; or env FLINK_PRINCIPAL_ID
}
```

If you prefer not to set a provider-wide `flink_principal_id`, set it per statement instead:

```terraform
resource "confluent_flink_statement" "create_table" {
  principal { id = var.flink_principal_id }   # <-- satisfies the same requirement
  statement = "CREATE TABLE ..."
  # ...
}
```

---

## 3. ARC self-hosted runners (in-VPC)

Deploy a runner scale set with ARC into the VPC/EKS. The pod subnet must resolve the
Confluent private DNS zone (see §6 — this is the #1 failure mode).

```yaml
# runner-scaleset.values.yaml  (helm: gha-runner-scale-set)
githubConfigUrl: https://github.com/<org>/<repo>
githubConfigSecret: arc-github-app          # GitHub App creds for ARC
minRunners: 0                               # ephemeral: scale to zero when idle
maxRunners: 6
containerMode:
  type: kubernetes
template:
  spec:
    # Schedule onto nodes in the subnet that has the PrivateLink path to Confluent.
    nodeSelector:
      confluent-private-access: "true"
    dnsPolicy: ClusterFirst                 # cluster CoreDNS must forward the Confluent PHZ
    containers:
      - name: runner
        image: ghcr.io/actions/actions-runner:latest
        env:
          - name: AWS_REGION
            value: us-east-2
```

> The runner nodes' resolver (CoreDNS → VPC resolver → Route 53 private hosted zone, or a
> `confluent_dns_forwarder`) must return the private IPs for `*.<region>.<cloud>.confluent.cloud`
> **and** the Schema Registry hostname. If it doesn't, plane-B applies fail with `no such host`.

---

## 4. GitHub Actions — OIDC auth, plane-aware jobs

```yaml
# .github/workflows/confluent-iac.yml
name: confluent-iac
on:
  pull_request: { paths: ['infra/**'] }
  push: { branches: [main], paths: ['infra/**'] }

permissions:
  id-token: write        # required for GitHub OIDC
  contents: read

jobs:
  platform:              # MANAGEMENT plane — public endpoints; hosted OR self-hosted
    runs-on: [self-hosted, confluent-arc]
    environment: platform-approval        # manual gate on apply
    defaults: { run: { working-directory: infra/platform } }
    steps:
      - uses: actions/checkout@v4
      # Exchange GitHub OIDC -> cloud role -> pull short-lived Confluent Cloud API key
      - uses: aws-actions/configure-aws-credentials@v4
        with: { role-to-assume: arn:aws:iam::<acct>:role/gh-confluent-platform, aws-region: us-east-2 }
      - run: |
          creds=$(aws secretsmanager get-secret-value --secret-id confluent/cloud/api --query SecretString --output text)
          echo "CONFLUENT_CLOUD_API_KEY=$(echo "$creds" | jq -r .key)" >> "$GITHUB_ENV"
          echo "CONFLUENT_CLOUD_API_SECRET=$(echo "$creds" | jq -r .secret)" >> "$GITHUB_ENV"
      - uses: hashicorp/setup-terraform@v3
      - run: terraform init && terraform plan -out tfplan
      - if: github.ref == 'refs/heads/main'
        run: terraform apply -auto-approve tfplan

  data:                  # DATA plane — private endpoints; MUST be the in-VPC runner
    needs: platform      # cluster + rest_endpoint must exist first
    runs-on: [self-hosted, confluent-arc]
    defaults: { run: { working-directory: infra/data } }
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with: { role-to-assume: arn:aws:iam::<acct>:role/gh-confluent-data, aws-region: us-east-2 }
      - run: |               # cluster-scoped + SR-scoped keys for the data plane
          echo "TF_VAR_cluster_api_key=$(aws secretsmanager get-secret-value --secret-id confluent/cluster/key --query SecretString --output text | jq -r .key)" >> "$GITHUB_ENV"
          echo "TF_VAR_cluster_api_secret=..." >> "$GITHUB_ENV"
      - uses: hashicorp/setup-terraform@v3
      - run: terraform init && terraform plan -out tfplan
      - if: github.ref == 'refs/heads/main'
        run: terraform apply -auto-approve tfplan
```

Both jobs run on the in-VPC pool for simplicity; only `data` strictly requires it. `data`
`needs: platform` so the cluster and its `rest_endpoint` exist before any topic is applied.

---

## 5. Third-party CDC Agent Landing Zone (e.g. Precisely)

Third-party CDC agents (e.g. Precisely Connect CDC) run **in-VPC** (or on-prem via the same private path) and
produce to Confluent Cloud over PrivateLink. Terraform does **not** manage the agents — it
manages the Confluent landing zone they write into. Almost all of it is **plane B** (private,
in-VPC runner), except the network/service-account scaffolding in plane A.

**Plane A (platform/) — scaffolding for the CDC agents:**
- The PrivateLink plane-A resources the CDC agents connect through (the same path the runner
  rides — co-locate the runner subnet here). **Tier-dependent, and PLATT is legacy:**
  - **Enterprise (FSI baseline):** `confluent_gateway` + `confluent_access_point` + your
    `aws_vpc_endpoint` (ingress PrivateLink Gateway). Do **not** use the legacy
    `confluent_private_link_attachment` — no new PLATTs after AWS 2026-02-12 / Azure+GCP
    2026-05-04. One gateway covers Kafka + SR + Flink.
  - **Dedicated:** `confluent_network` (type `PRIVATELINK`) + `confluent_private_link_access`.
  - **DNS:** wire the two-step CNAME + wildcard access-point zone into the runner's resolver
    for **both** Kafka and SR (see §6). If agents are **on-prem/mainframe**, they can't reach
    PL directly — route through a shared-services VPC you own, then PL; co-locate the runner there.
- A **dedicated service account per CDC agent/app**: `confluent_service_account` +
  `confluent_api_key` (cluster-scoped) for the agent to authenticate as. Least privilege — one
  SA per agent, never shared.

**Plane B (data/) — what the CDC pipeline needs:**

```terraform
# One topic per CDC source table. Canon: RF3, min.insync.replicas=2,
# naming <domain>.<entity>.<event> (see topic-naming.md).
resource "confluent_kafka_topic" "cdc_customer" {
  topic_name    = "corebanking.customer.change"
  partitions_count = 6
  config = { "min.insync.replicas" = "2", "cleanup.policy" = "delete" }
  # provider = confluent  (data-plane alias, bound to the private rest_endpoint)
}

# CDC payload schema — Avro/Protobuf, BACKWARD compat, registered against the PRIVATE SR.
resource "confluent_schema" "cdc_customer_value" {
  subject_name = "corebanking.customer.change-value"
  format       = "AVRO"
  schema       = file("${path.module}/schemas/customer.avsc")
}

# Least-privilege ACLs for the CDC agent's service account.
resource "confluent_kafka_acl" "cdc_agent_write" {
  resource_type = "TOPIC"
  resource_name = "corebanking."          # prefix
  pattern_type  = "PREFIXED"
  principal     = "User:${data.terraform_remote_state.platform.outputs.cdc_agent_sa_id}"
  operation     = "WRITE"
  permission    = "ALLOW"
  host          = "*"
}
```

**CDC-agent-specific notes:**
- **Schema Registry needs its own private DNS resolution** from the runner — the CDC schema
  registration (`confluent_schema`) fails with `no such host` on the SR hostname even when
  Kafka resolves fine. Verify both.
- Give the CDC agent SA **WRITE on its topic prefix + SR write on its subject prefix** only —
  not cluster-wide. RBAC role bindings scoped by `crn_pattern`.
- If the CDC agent targets the mainframe (e.g. z/OS CDC via Precisely Connect CDC / SQData), the produce
  path is agent → CC over PrivateLink; Terraform's job stops at the CC landing zone. Do not try
  to model the agent in TF.
- Topic + schema changes for new CDC tables are the **high-churn plane-B PRs** — this is the
  workflow app/data teams use day to day; keep plane A (network/cluster) behind manual approval.

---

## 6. Verify (before declaring done)

1. **Plane A applies from CI** → environment, network, PL attachment, cluster present in the
   Console; `terraform output cluster_rest_endpoint` shows a **private** hostname.
2. **Runner resolves private DNS** → from a runner pod: `nslookup <cluster_rest_endpoint host>`
   and the SR host both return **private** IPs. This is the make-or-break check.
3. **Runner can actually reach the private endpoint (not just resolve it)** → from a runner
   pod: `nc -vz <private-IP> 443` against the IP the host resolved to. A timeout here — even
   though DNS returned a private `10.x` address — means a security-group / AZ / route problem,
   not DNS (§7). Confirm the endpoint's SG allows `tcp/443` from the runner CIDR and that the
   pod's AZ has an endpoint ENI.
4. **Plane B applies from CI** → a test topic + schema + ACL created; confirm in the Console.
   If you also manage Flink, a test `confluent_flink_statement` applies (needs the Flink
   provider block + principal, §2).
5. **OIDC, no static keys** → confirm no `CONFLUENT_CLOUD_API_KEY` in GitHub repo/org secrets;
   creds come from the secrets manager at run time.
6. **CDC agent path** → the CDC agent SA can WRITE to its topics (produce a test CDC record);
   ACLs deny everything else.

---

## 7. Failure modes & fixes

| Symptom | Cause | Fix |
|---|---|---|
| `dial tcp <public-IP>:443 i/o timeout`, or no route at all | Job ran on a GitHub-hosted (public) runner | Pin the `data` job to `[self-hosted, confluent-arc]` |
| `dial tcp <private-IP e.g. 10.x>:443 i/o timeout` — **DNS resolved to a private IP but the connection times out** | Reachability, not DNS: endpoint SG blocks 443 from the runner CIDR, **or** the runner pod is in an AZ with no endpoint ENI, **or** missing route/NACL | Allow `tcp/443` from the runner CIDR on the PrivateLink endpoint SG; ensure the ARC node pool spans the endpoint AZs; check route table/NACL. Verify with `nc -vz <private-IP> 443` |
| `no such host` for `rest_endpoint` or SR host | Private DNS not resolvable from runner pods | Forward the Confluent private hosted zone through CoreDNS / `confluent_dns_forwarder` |
| `error creating Flink Statement: one of provider.flink principal id … or resource.principal.id must be set` | `confluent_flink_statement` has no principal to run as | Set `flink_principal_id` on the data-plane provider (or `FLINK_PRINCIPAL_ID` env), **or** a `principal { id = … }` block on the resource (§2) |
| Half-applied (cluster made, topics failed) | Single apply, both planes, public runner | Split state; `data` `needs: platform` |
| Plane-A `403` from CI | `confluent_ip_filter` excludes runner egress IP | Add NAT EIP to an allowlisted `confluent_ip_group` |
| Topic "can't authenticate" despite valid cloud key | `cloud_api_key` used where a cluster-scoped key + `rest_endpoint` is required | Use the data-plane provider alias with the cluster key |
| CDC agent SA can't produce | ACL/RBAC too narrow or wrong principal | Grant WRITE on the topic prefix + SR write on the subject prefix, scoped by `crn_pattern` |
| State lock stuck | Prior run killed mid-apply | Release the DynamoDB/GCS lock; re-run |

---

## 8. Operations

- **Provider pin:** hold `confluentinc/confluent = 2.80.0` in CI; bump deliberately with a plan-only PR first.
- **Credential rotation:** OIDC tokens are short-lived (good); rotate the underlying cluster/SR
  API keys on schedule via plane A and update the secrets-manager entry — a silent expiry stalls
  plane-B applies.
- **State hygiene:** SSE-KMS + versioning + IAM-restricted; reach the backend via VPC endpoint.
  State holds API-key secrets — treat as sensitive, audit access (CloudTrail/GCS logs).
- **Least privilege:** separate identities for plane A (`EnvironmentAdmin`, `crn_pattern`-scoped)
  and plane B (cluster-scoped); a distinct SA per CDC agent.
- **Guardrails:** `prevent_destroy` on environment/cluster/network; manual approval gate on the
  `platform` job; app teams only PR into `data/`.
