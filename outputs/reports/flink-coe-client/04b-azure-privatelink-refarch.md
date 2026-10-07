> Part of **Flink Center of Excellence — Managed Flink on Confluent Cloud** (self-contained series). Validated against Confluent documentation 2026-09-08.

# Part 4b — Azure VNet / Private Link Reference Architecture

Two network paths matter, and only one is yours to wire.

1. **Flink → Kafka: always internal to Confluent Cloud.** This path never traverses Private Link or the public internet and requires no configuration. The compute pool reaches the cluster over Confluent's internal fabric.
2. **Client → Flink: Private Link-governed.** SQL Workspaces (Console), the Flink shell/CLI, `confluent_flink_statement` (Terraform), and the REST API all reach the Flink control-plane endpoint — that path is what you make private.

Managed Flink supports private networking on Azure in **all regions that support Flink**.

## Do you need a separate Private Link for Flink?

| Cluster type | Separate Flink gateway? | Shape |
|---|---|---|
| **Enterprise** | **No** — reuse the one ingress PrivateLink Gateway | One private endpoint / one Private Link Service covers Kafka + Flink + Schema Registry |
| **Dedicated** (Private Link, VNet Peering, or ExpressRoute for Kafka) | **Yes** — Flink requires its own gateway in the **same region**, even where a private link already exists for the Dedicated cluster | Two private endpoints, each targeting a different Confluent Private Link Service alias |

- **Gateway model:** the older Private Link Attachment (PLATT) was superseded by the **ingress PrivateLink Gateway** — the **Azure cutover was 2026-05-04** (AWS was earlier, 2026-02-12). Existing PLATTs continue to function, but new ones should use the gateway model. The gateway issues a unique FQDN per Private Link connection, which is what lets you route VNet traffic to specific services rather than one flat endpoint.
- **Third option — Confluent Cloud network (CCN):** available on **Azure and AWS only** (not Google Cloud). If you already run a Dedicated cluster in the target environment and region, Flink can ride the existing Confluent Cloud network with no additional networking work. Consider this first for Azure Dedicated estates; it is usually the shortest path.
- **Egress Private Link** (niche): for Flink statements reaching *out* to an external service — Azure Blob Storage for external tables, Azure OpenAI for AI inference, Azure Key Vault, or any service you expose behind an Azure Private Link service. Implemented as **Azure Private Endpoints**, available on Enterprise clusters.

## Three Azure constraints with no AWS equivalent

These are the differences that change the design, not just the resource names. Read them before drawing the topology.

1. **One VNet connects to exactly one Confluent Cloud environment.** On AWS, a single VPC can connect to multiple Confluent Cloud environments; **on Azure it cannot**. If your environment boundary is dev / staging / prod (it should be), each needs its own VNet — or its own spoke in a hub-and-spoke, with the private endpoint and Private DNS Zone landing in the spoke. Design the environment-to-VNet mapping before provisioning; retrofitting it means rebuilding endpoints and DNS zones.
2. **The access point is regional — there is no zonal alignment.** One private endpoint routes traffic for all availability zones. This removes the most common AWS failure mode outright (a runner landing in an AZ that has no endpoint). Note the asymmetry: **Dedicated Kafka clusters still require zonal alignment** with separate zonal private endpoints and `*.az1` / `*.az2` / `*.az3` records. Access points do not — a single `*` wildcard record covers every hostname under the domain, including the zonal broker variants.
3. **Network policies on the private endpoint default to Disabled.** Azure's "Network policy for private endpoints" setting is off by default, which means **NSGs and UDRs are not applied to the endpoint** until you enable it. This is the opposite default from an AWS security group, and it has two consequences: a connection failure is *less* likely to be endpoint-level filtering than it would be on AWS, and FSI environments that require NSG enforcement at the endpoint must deliberately turn the policy on — at which point NSG rules become a live failure mode. Set this to the organization-mandated value explicitly rather than accepting the default.

Two further limits apply to every gateway: it cannot span **cloud regions** or **Confluent Cloud environments**, and it supports up to **10 private endpoints**.

## Azure wiring

Four resources, in order. Steps 1 and 3 are Confluent-side; step 2 is Azure-side; step 4 is DNS.

1. **Ingress PrivateLink Gateway** (Confluent) — created per environment and region. Record the **Private Link Service ID** or **Private Link Service Alias** it issues; you need it for the next step. The gateway goes to `CREATED`, then `READY` once an access point is attached. It goes to `EXPIRED` if no valid access point is provisioned in time — at which point you create a new gateway.
2. **Azure private endpoint** (Azure) — in the VNet and subnet where your clients live. Connection method is **"Connect to an Azure resource by resource ID or alias"**, pasting the Private Link Service ID or Alias from step 1. Allocate the IP dynamically. Set **Network policy for private endpoints** to your organization's mandated value (see constraint 3 above; the default is Disabled). Record the private endpoint's Azure resource ID.
3. **Ingress PrivateLink Access Point** (Confluent) — registers that private endpoint's resource ID back to the gateway. Verify in the Azure portal that the private endpoint connection status becomes **Approved**; the gateway and access point then move to `READY`.
4. **Azure Private DNS Zone** (Azure) — named with the **DNS domain value shown on the gateway** in the Confluent Cloud Console. Add one record set: name `*`, type `A`, TTL `1 minute`, pointing at the private IP of the endpoint's network interface. Then **link the zone to every VNet** where clients or CI/CD runners run ("Virtual network links").

**On DNS resolution.** The client's network must still permit **public DNS resolution** — Confluent advertises the access-point hostnames in the public resolver, and they CNAME into your private zone. Resolution is two steps: Confluent's Global DNS Resolver returns a CNAME that strips the `glb` subdomain and turns the access point ID into a subdomain —

```
$lkc-id-$accesspointId.$region.azure.accesspoint.glb.confluent.cloud
  → $lkc-id.$accesspointId.$region.azure.accesspoint.confluent.cloud
```

— and your Private DNS Zone then resolves that name to the private endpoint. **Wildcard the zone; never hardcode broker or endpoint names.** Broker names retrieved from cluster metadata are not static.

### Endpoints you will actually connect to

| Networking | Cluster type | Flink endpoints |
|---|---|---|
| Private Link (ingress PrivateLink Gateway) | Enterprise | `flink.<region>.azure.private.confluent.cloud` <br> `flinkpls.<region>.azure.private.confluent.cloud` |
| Confluent Cloud network | Dedicated | `flink.dom<id>.<region>.azure.confluent.cloud` <br> `flinkpls.dom<id>.<region>.azure.confluent.cloud` |
| Public (default, always present) | any | `flink.<region>.azure.confluent.cloud` |

`flinkpls` is the **Language Service** endpoint — SQL autocomplete and validation in the Workspaces editor. It is a separate hostname from `flink` and is covered by the same wildcard record, but if you are allowlisting hostnames explicitly rather than wildcarding, omitting it produces a Workspaces editor that loads but cannot validate SQL.

Retrieve the live values with `confluent flink endpoint list`, or from the Flink **Endpoints** page in the Console.

## Deployment flow (the FSI pattern)

- **Developers get no direct CLI/Console access to production.** All Flink SQL is version-controlled and deployed by a **self-hosted CI/CD runner inside the customer VNet** — an Azure DevOps self-hosted agent or a self-hosted GitHub Actions runner — which calls `confluent_flink_statement` (preferred, infrastructure-as-code) or the REST API over the private endpoint.
- Because the Flink control-plane endpoint (`flink.<region>.azure.private.confluent.cloud`) is a private target, the runner must **resolve it** (the Private DNS Zone is linked to the runner's VNet, and public DNS resolution is not blocked) and **reach it** (TCP/443 permitted to the endpoint's private IP by whatever NSG, Azure Firewall, or UDR sits in the path). Unlike AWS, the runner does **not** need to be placed in a specific availability zone.
- Where the runner sits in a hub-and-spoke topology, confirm the Private DNS Zone is linked to the **runner's** VNet specifically — a link to the workload spoke does not resolve from the hub, and vice versa.
- Optionally pair this with **IP Filtering** set to the predefined **No Public Networks** group (`ipg-none`) on Flink resources, which blocks all public access to statements and workspaces and leaves only the private path. IP filters apply to public requests only and do not constrain traffic arriving over Private Link.

## Two common failure modes on this path

- **`dial tcp <private-IP>:443: i/o timeout`** — DNS resolved to a private address but the connection timed out. This is reachability, not DNS. On Azure the usual causes are an Azure Firewall or UDR intercepting the path, or an NSG blocking 443 *if* network policies for private endpoints have been enabled on the subnet. Confirm with `nc -vz <private-IP> 443`. Note that the AWS version of this failure — the runner sitting in an availability zone with no endpoint — does **not** apply on Azure, because the access point is regional.
- **`no such host`** for the Flink or Schema Registry hostname — the Private DNS Zone is not resolvable from the runner. Either the zone is not linked to the runner's VNet, or public DNS resolution is blocked and the first CNAME hop cannot complete. Check the virtual network link before anything else; it is the single most common cause.

---

### Validation status for this part

Validated against Confluent documentation on **2026-09-08** (`flink/concepts/flink-private-networking`, `networking/azure-platt`; both last published 2026-08-31): Azure private-networking support across all Flink regions; the three connectivity options and their cloud availability; the Enterprise-reuse / Dedicated-separate-gateway rule; the 2026-05-04 Azure PLATT-to-gateway cutover; the one-VNet-to-one-environment constraint; the 10-endpoint and same-region/same-environment gateway limits; the four-resource provisioning sequence and gateway state machine; the two-step CNAME resolution and wildcard `A` record; access-point regionality versus Dedicated zonal alignment; the private-endpoint network-policy default; the `flink` / `flinkpls` endpoint patterns; and Egress Private Link on Azure.

**(unverified):** Azure Internal Load Balancer idle-timeout behavior is sometimes raised on this topic. The architectural claim that the Private Link path does not traverse an ILB is sound, but specific timeout values were not confirmed against current Azure documentation and should be validated before being used in a customer commitment.
