---
title: Flink PrivateLink Gateway Setup & Troubleshooting Runbook
subtitle: Stand up an ingress PrivateLink Gateway for Confluent Cloud for Apache Flink on AWS, end to end, using scoped-zone DNS that can never collide with a co-located Kafka PNI cluster
audience: Platform / cloud networking engineers enabling private connectivity to Flink
validated: 2026-09-18 against docs.confluent.io (flink/concepts/flink-private-networking.html, flink/operate-and-deploy/private-networking.html, networking/aws-platt.html, networking/testing.html) and live AWS Route 53 behavior confirmed via VPC-internal resolution testing
confidence: high
related-canon: wiki/patterns/flink-coe-aws-privatelink-refarch.md, wiki/concepts/confluent-cloud-private-networking.md
---

# Flink PrivateLink Gateway Setup & Troubleshooting Runbook

**Purpose:** Stand up an ingress PrivateLink Gateway on AWS so Flink SQL clients (Console, CLI,
Terraform, REST API) reach Confluent Cloud for Apache Flink privately, and fix the two most common
failure modes — "it keeps defaulting to public" and "the private endpoint doesn't show up in the
list even though it's Ready."

**Scope note:** this gateway only secures **client → Flink control-plane** traffic. Flink → Kafka
traffic always routes internally within Confluent Cloud regardless of the Kafka cluster's own
networking (PNI, Peering, Transit Gateway, PrivateLink) — so having private networking on the
Kafka cluster does **not** give Flink private connectivity by itself. For **Dedicated** clusters,
Flink needs its own gateway in the same region even if the cluster already has a private link. For
**Enterprise** clusters, one gateway covers Kafka + Flink + Schema Registry + Connect.

**DNS design note (read before step 4):** Confluent issues Flink and Kafka PNI hostnames from a
*shared* parent domain (`<region>.<cloud>.accesspoint.glb.confluent.cloud`). This runbook's DNS
step scopes each private hosted zone to the **exact** Flink hostname it serves, never to the shared
parent — so it is structurally impossible for this setup to collide with a co-located Kafka PNI
cluster, now or later, no matter how Confluent rotates broker IDs. If you're fixing an environment
that already has a broad wildcard zone from an older version of this runbook, see the **Migration**
section near the end instead of starting from step 4.

---

## 0. Prerequisites

- Confluent Cloud role: `OrganizationAdmin`, `EnvironmentAdmin`, or `NetworkAdmin` on the target
  environment.
- A VPC in AWS in the same region as the Flink usage.
- Confirm which connectivity model applies (Enterprise = reuse existing gateway; Dedicated =
  separate Flink-specific gateway, same region as the cluster's own PrivateLink/Peering/TGW/PNI
  connection).

## 1. Create the ingress PrivateLink Gateway

**Console:** Environments → select environment → **Network management** → **For serverless
products** tab → **+Add gateway configuration** → type **PrivateLink** → **+Create configuration**
→ name it, cloud provider `AWS`, region = your VPC's region → **Submit**.

Note the **PrivateLink Service ID** shown on the **2. Access point** tab — you need it in step 2.
The gateway is now in `CREATED` state (not yet `READY` — that happens after the access point is
attached and the VPC endpoint connection is accepted).

**CLI:**
```bash
confluent network gateway create my-ingress-gateway \
  --cloud aws \
  --region <region> \
  --type ingress-privatelink
```

**Terraform:**
```hcl
resource "confluent_gateway" "aws_ingress" {
  display_name = "my-gateway"
  environment {
    id = "env-123abc"
  }
  aws_ingress_private_link_gateway {
    region = "us-west-2"
  }
}
```

If you already created the gateway and lost the Service ID, retrieve it again with
`confluent network gateway describe <gateway-id>` (REST: `status.cloud.vpc_endpoint_service_id`)
rather than recreating the gateway.

## 2. Create the AWS VPC interface endpoint

Target the **PrivateLink Service ID** from step 1. Pick subnets across the AZs your Flink
clients/CI runners actually run in — minimum 2 for HA; you don't need every AZ in the region, and
this is separate from the "10 VPC endpoints per gateway" cap (that limits distinct endpoints, not
subnets within one).

```bash
aws ec2 create-vpc-endpoint \
  --vpc-id <vpc-id> \
  --service-name com.amazonaws.vpce.<region>.<privatelink-service-id> \
  --subnet-ids <subnet-id-1> <subnet-id-2> \
  --region <region> \
  --no-private-dns-enabled \
  --vpc-endpoint-type Interface
```

Notes:
- `--subnet-ids` is **space-separated**, not comma-separated.
- `--no-private-dns-enabled` is required, not optional — DNS for this endpoint is handled entirely
  by the scoped Route 53 zones in step 4; AWS's auto-managed private DNS would fight that scheme.
- Security group: inbound + outbound TCP `443` from your VPC CIDR. (Flink never exposes a raw
  broker port — everything is HTTPS/WSS on 443, unlike Kafka's `9092`.)
- Note the returned VPC Endpoint ID (`vpce-...`) — needed next, and again in step 4.

## 3. Create the PrivateLink Access Point

Registers the VPC endpoint against the gateway.

**CLI:**
```bash
confluent network access-point private-link ingress-endpoint create my-ingress-access-point \
  --cloud aws \
  --gateway <gateway-id> \
  --vpc-endpoint-id <vpce-id>
```

**Terraform:**
```hcl
resource "confluent_access_point" "aws_ingress_1" {
  display_name = "my_access_point"
  environment {
    id = "env-123abc"
  }
  gateway {
    id = "gw-123abc"
  }
  aws_ingress_private_link_endpoint {
    vpc_endpoint_id = "vpce-1234567890abcdef0"
  }
  depends_on = [confluent_gateway.aws_ingress]
}
```

Gateway + access point reach `READY` only after AWS accepts the VPC endpoint connection — if your
PrivateLink service requires manual connection acceptance, accept it on the AWS side or it'll sit
in `PendingAcceptance`/`CREATED` indefinitely and never go private.

## 4. Configure DNS (scoped Route 53 private hosted zones — one per Flink hostname)

Grab the gateway's DNS domain from the Access Point tab in Console. Flink exposes exactly two
hostnames under it that this gateway needs to serve privately:

- `flink-<access-point-id>.<region>.<cloud>.accesspoint.glb.confluent.cloud` (SQL/statements)
- `flinkpls-<access-point-id>.<region>.<cloud>.accesspoint.glb.confluent.cloud` (SQL shell
  autocomplete/language service — separate hostname, separate record, easy to miss)

Get the VPC endpoint's regional DNS name and its Route 53 hosted zone ID (needed for an alias
target, not a literal CNAME value):

```bash
aws ec2 describe-vpc-endpoints \
  --vpc-endpoint-ids <vpce-id> \
  --region <region> \
  --query 'VpcEndpoints[0].DnsEntries[0].{DnsName:DnsName,HostedZoneId:HostedZoneId}' \
  --output json
```

**Why one zone per hostname instead of one zone for the whole domain:** a Route 53 private hosted
zone is authoritative for *everything* under the name it's associated with, for every resource in
that VPC — including names Confluent hasn't even created yet. If you scope the zone to the shared
parent domain (`<region>.<cloud>.accesspoint.glb.confluent.cloud`) and cover it with a wildcard,
you also capture every Kafka PNI bootstrap and per-broker hostname that happens to live under the
same parent in that VPC, permanently shadowing them from public DNS with no fallback — and Kafka
PNI broker IDs churn (scaling, rebalances, replacement) so there is no static list of hostnames you
could enumerate instead. Scoping the zone to the *exact* hostname sidesteps the problem entirely:
nothing else under the parent domain is ever touched, so Kafka (or anything else Confluent adds
later) always falls through to normal public DNS resolution, unaffected, forever.

Create one private hosted zone per Flink hostname:

```bash
aws route53 create-hosted-zone \
  --name "flink-<access-point-id>.<region>.<cloud>.accesspoint.glb.confluent.cloud" \
  --vpc VPCRegion=<region>,VPCId=<vpc-id> \
  --hosted-zone-config Comment="Confluent Cloud PrivateLink DNS - Flink SQL, scoped to this hostname only",PrivateZone=true \
  --caller-reference "flink-zone-$(date +%s)"

aws route53 create-hosted-zone \
  --name "flinkpls-<access-point-id>.<region>.<cloud>.accesspoint.glb.confluent.cloud" \
  --vpc VPCRegion=<region>,VPCId=<vpc-id> \
  --hosted-zone-config Comment="Confluent Cloud PrivateLink DNS - Flink SQL shell, scoped to this hostname only",PrivateZone=true \
  --caller-reference "flinkpls-zone-$(date +%s)"
```

The zone's apex name **is** the hostname you need a record for, so a plain CNAME won't work here —
DNS doesn't allow a CNAME to coexist with the zone's own SOA/NS at the apex. Use a Route 53 **alias
A record** instead, which Route 53 supports natively for VPC interface endpoint targets:

```bash
cat > flink-alias.json <<EOF
{
  "Changes": [{
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": "flink-<access-point-id>.<region>.<cloud>.accesspoint.glb.confluent.cloud.",
      "Type": "A",
      "AliasTarget": {
        "HostedZoneId": "<vpc-endpoint-hosted-zone-id-from-describe-vpc-endpoints>",
        "DNSName": "<vpc-endpoint-dns-name>.",
        "EvaluateTargetHealth": true
      }
    }
  }]
}
EOF

aws route53 change-resource-record-sets \
  --hosted-zone-id <flink-hosted-zone-id> \
  --change-batch file://flink-alias.json
```

Repeat for `flinkpls-<access-point-id>...` against its own hosted zone. Both alias targets point at
the same VPC endpoint — Console and SQL shell traffic share one interface endpoint, just two
different hostnames.

Check propagation and correctness:
```bash
aws route53 get-change --id <change-id>          # look for Status: INSYNC
aws route53 list-resource-record-sets --hosted-zone-id <flink-hosted-zone-id>
```

## 5. Verify connectivity (from a host inside the VPC)

```bash
export FLINK_ENDPOINT=flink-<access-point-id>.<region>.<cloud>.accesspoint.glb.confluent.cloud
dig $FLINK_ENDPOINT

openssl s_client -connect $FLINK_ENDPOINT:443 -servername $FLINK_ENDPOINT \
  -verify_hostname $FLINK_ENDPOINT </dev/null 2>/dev/null \
  | grep -E 'Verify return code|BEGIN CERTIFICATE' | xargs
```
Expect `-----BEGIN CERTIFICATE----- Verify return code: 0 (ok)`.

Test the SQL shell / language-service endpoint too — separate hostname, separate record, easy to
skip by accident:
```bash
export FLINKPLS_ENDPOINT=flinkpls-<access-point-id>.<region>.<cloud>.accesspoint.glb.confluent.cloud
openssl s_client -connect $FLINKPLS_ENDPOINT:443 -servername $FLINKPLS_ENDPOINT \
  -verify_hostname $FLINKPLS_ENDPOINT </dev/null 2>/dev/null \
  | grep -E 'Verify return code|BEGIN CERTIFICATE' | xargs
```

If there's a co-located Kafka PNI cluster in this VPC, confirm it's unaffected — resolve its
bootstrap and a couple of broker hostnames the same way. They should resolve via public DNS exactly
as they would outside the VPC, since the scoped zones above never touch their names:
```bash
dig <kafka-bootstrap-hostname>
dig <any-kafka-broker-hostname>
```

## 6. Select the private endpoint in the Confluent CLI

**The CLI defaults to the public Flink endpoint even when a private one exists and is Ready** —
this is not automatic. You must explicitly select region and endpoint every time:

```bash
confluent environment use <env-id>                                # must match the gateway's env
confluent flink region use --cloud <cloud_provider> --region <region>  # must match gateway's region
confluent flink endpoint list                                     # both public + private now visible
confluent flink endpoint use                                      # pick the private one
```

If the private endpoint doesn't appear in `endpoint list` at all (even though Console shows
Ready), it's almost always an environment/region mismatch below, not a real provisioning failure.

## 7. Troubleshooting checklist

| Symptom | Likely cause |
|---|---|
| Console/CLI keeps using public endpoint | CLI endpoint never explicitly selected (step 6); client not actually inside the VPC/VNet or via proxy; DNS not resolving privately |
| Private endpoint missing from `confluent flink endpoint list` | `confluent environment use` / `confluent flink region use` don't match the environment+region the gateway lives in — the list is scoped to current CLI context |
| `dig $FLINK_ENDPOINT` fails or returns public IP | Private hosted zone not associated with the VPC; alias record missing/wrong `HostedZoneId`; VPC not using standard DNS resolver — test with `dig @169.254.169.253 <hostname>` (AWS resolver; Azure `168.63.129.16`, GCP `169.254.169.254`) |
| `dig` succeeds but TLS test fails | Security group missing inbound/outbound `443` from VPC CIDR |
| Gateway stuck in `CREATED`, never `READY` | AWS VPC endpoint connection sitting in `PendingAcceptance` — accept it on the AWS side, or the PrivateLink service auto-accept setting is off |
| Works for Console, fails in SQL shell | `flinkpls-*` hostname/zone/record missing — SQL shell needs its own zone in addition to `flink-*` |
| DNS was just fixed but a specific hostname still fails to resolve for several minutes | **Stale negative cache**, not a config problem. Route 53 Resolver caches `NXDOMAIN` answers (TTL driven by the zone's SOA, commonly up to 900s) and does **not** invalidate that cache when the underlying zone/record changes — it only expires on its own. Confirm the fix is actually correct by testing a hostname that was *never* queried before (or was never in a failing state); if that resolves cleanly, the config is right and the still-failing hostname just needs its stale cache entry to time out. |
| Kafka PNI bootstrap/broker hostnames fail to resolve (or resolve to the Flink VPC endpoint) in a VPC that also has this gateway | The private zone(s) in this VPC are scoped too broadly and are shadowing Kafka's hostnames. This shouldn't happen if you followed step 4 as written (each zone's apex is one exact Flink hostname). If it's happening anyway, an older/broader zone exists in this VPC — go to **Migration** below. |

### Do NOT use NS delegation to `glbns1`/`glbns2.confluent.cloud` as a fix

An earlier version of this runbook recommended adding NS delegation records inside the private zone
for Kafka's per-broker AZ subtrees, pointing at Confluent's own GSLB nameservers
(`glbns1.confluent.cloud`, `glbns2.confluent.cloud`), reasoning that Route 53 Resolver would follow
the delegation out to them. **This does not work and should not be used.** Route 53 Resolver serves
private hosted zones authoritatively; for a namespace it's authoritative for, it returns whatever
NS records exist there as a literal referral — it does not itself act as a recursive resolver
chasing that delegation out to a third-party (non-Route 53) nameserver. In practice this means
queries for names under the delegated subtree come back with the NS records themselves instead of
an address, which every real DNS client (including librdkafka/the Confluent CLI) treats as a
resolution failure. There is no fix that keeps a broad zone *and* adds delegation — the only
reliable fix is not owning that namespace at all, per step 4.

## Migration: replacing a pre-existing broad/wildcard zone

If a broad private hosted zone already exists in this VPC (scoped to the shared
`<region>.<cloud>.accesspoint.glb.confluent.cloud` parent, likely with a wildcard CNAME and/or NS
delegation records left over from an older setup), migrate to the scoped-zone design without a
resolution gap:

1. **Create the two scoped Flink zones** as in step 4 (new zones, new alias records), while the old
   broad zone is still live. Verify both resolve correctly from inside the VPC before touching
   anything else — Route 53 always matches the most specific zone for a query, so the new narrow
   zones take precedence over the old broad one the moment they're associated with the VPC, with no
   conflict between them.
2. **Verify Kafka is unaffected by the new zones** — `dig` its bootstrap hostname and a couple of
   broker hostnames from inside the VPC; they should still resolve through the old broad zone at
   this point (that's expected — it isn't gone yet).
3. **Strip every non-default record from the old broad zone**, then **delete the zone itself**:
   ```bash
   aws route53 change-resource-record-sets \
     --hosted-zone-id <old-broad-zone-id> \
     --change-batch file://teardown-change-batch.json   # DELETE action for every record except the zone's own default SOA/NS

   aws route53 delete-hosted-zone --id <old-broad-zone-id>
   ```
4. **Re-verify everything from inside the VPC** — Flink via the new scoped zones, and Kafka now
   falling through to public DNS with no private zone in the way at all:
   ```bash
   dig flink-<access-point-id>.<region>.<cloud>.accesspoint.glb.confluent.cloud
   dig flinkpls-<access-point-id>.<region>.<cloud>.accesspoint.glb.confluent.cloud
   dig <kafka-bootstrap-hostname>
   dig <a-kafka-broker-hostname-that-previously-failed>
   dig <a-kafka-broker-hostname-that-has-never-been-queried-before>   # proves fallthrough works generally, not just for cached-good names
   ```
   If a specific previously-failing hostname is still `NXDOMAIN` right after the delete, that's the
   stale-negative-cache row in the troubleshooting table above, not a sign the migration failed —
   confirm via the never-queried-before hostname, which has no stale cache to clear.
5. If you deleted a wildcard/broad zone for this exact reason once before and it came back, check
   CloudTrail (`ChangeResourceRecordSets` events on the hosted zone) before deleting again — someone
   else with access to the zone may not know why it needs to go, and will keep re-adding it. Loop
   them in.

## Caveats

- One PrivateLink Gateway per environment+region — it doesn't span regions or environments.
- Enterprise clusters reuse one gateway for Kafka + Flink + SR + Connect; Dedicated clusters need
  a **separate** Flink gateway even when the cluster already has private connectivity, because
  the gateway secures client→Flink, not Flink→Kafka.
- `--no-private-dns-enabled` on the VPC endpoint is mandatory, not a suggestion — the scoped Route
  53 zones in step 4 depend on AWS not auto-managing this.
- As of 2026-02-12 the PrivateLink Attachment (PLATT) resource was replaced by the ingress
  PrivateLink Gateway resource. Existing PLATTs still function but new provisioning should use
  gateways.
- Never scope a private hosted zone to the shared `<region>.<cloud>.accesspoint.glb.confluent.cloud`
  parent domain, and never use a wildcard record within it — that domain is shared with every other
  Confluent Cloud PrivateLink/PNI resource in the account for that region, present and future.
  Scope zones to the exact hostname you need, per step 4, every time.
- Route 53 Resolver does not follow NS delegation inside a private hosted zone out to third-party
  (non-Route 53) nameservers — it returns the NS records as a referral instead of an address. Don't
  use NS delegation as a workaround for anything under this domain.

## Related

- [wiki/patterns/flink-coe-aws-privatelink-refarch.md](../../wiki/patterns/flink-coe-aws-privatelink-refarch.md) —
  reference-architecture framing (Enterprise vs Dedicated gateway model, DevOps/CI-CD-over-PrivateLink pattern)
- [wiki/concepts/confluent-cloud-private-networking.md](../../wiki/concepts/confluent-cloud-private-networking.md) —
  gateway mechanics and per-tier connectivity matrix
- [outputs/runbooks/terraform-cicd-confluent-private-networking-runbook.md](terraform-cicd-confluent-private-networking-runbook.md) —
  the in-VPC CI/CD runner model that consumes this same private endpoint for `confluent_flink_statement` deploys
