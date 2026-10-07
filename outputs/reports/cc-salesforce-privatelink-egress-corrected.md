# Confluent Cloud → Salesforce via AWS PrivateLink (Salesforce Private Connect)

*Corrected 2026-08-07 against Confluent docs (`connectors/networking/aws-eap-self-managed`, egress-PrivateLink canon). Confluent-side networking steps validated; items marked **⚠️ Confirm** could not be verified this session (Salesforce connector docs unreachable) and are Salesforce-side details to check before relying on them.*

When establishing this link, the terminology between the two platforms can often be confusing. Because data flows out of Confluent Cloud and into Salesforce, this is an **Egress** connection from Confluent Cloud's perspective, but an **Inbound** connection from Salesforce's perspective.

Here is the exact sequence to establish the secure tunnel using AWS PrivateLink (the underlying technology for Salesforce Private Connect).

> **⚠️ Confirm (target-service model).** Confluent documents egress-PrivateLink flows for **first-party services**, **self-managed services you host** (you build the NLB + endpoint service), **Amazon RDS**, and **Amazon DocumentDB**. Salesforce is a **third-party SaaS that publishes its own AWS PrivateLink endpoint service**, so you consume it via the **"Other"** service option (paste its service name) — an adaptation of the self-managed flow in which Salesforce, not you, owns the load balancer and endpoint service. Confirm Salesforce Private Connect exposes an AWS endpoint service you can target from your region.

## Prerequisites — cluster, network, and AWS-side settings

Egress PrivateLink for fully-managed connectors requires **one** of the following Confluent Cloud network setups:

- **Dedicated cluster** with a Confluent Cloud network whose **Connection type is "PrivateLink Access"** — the walkthrough below (Egress connections / Egress DNS tabs) is this path.
- **Enterprise cluster** with a **network gateway for outbound connectivity** — the UI differs: **Network Management → "For serverless products" tab → the gateway → Access points → Add access point** (and DNS records under the gateway's **DNS** tab). The field values and endpoint-service model are otherwise the same.
- Alternatively, **Private Network Interface (PNI)** routes connector traffic through ENIs in your AWS account without PrivateLink infrastructure (available for Enterprise and Freight clusters) — a different mechanism, out of scope here.

Note the two AWS-side settings on the **endpoint-service** side (see §7 — these are the most common cause of a "Ready but won't connect" endpoint): the endpoint service must not enforce inbound rules that block Confluent, and **cross-zone load balancing** must be enabled if the service's availability zones don't overlap Confluent's endpoint AZs. For a SaaS provider like Salesforce, these live on **Salesforce's** side of the connection.

## 1. Retrieve the Salesforce Endpoint Service Name

You first need to find the specific AWS service name where Confluent Cloud should point its outbound traffic.

1. Log in to your Salesforce organization as an Administrator.
2. Navigate to **Setup > Security > Private Connect**.
3. Under the **AWS Regions** section, locate the region that matches your Confluent Cloud cluster (e.g., `us-east-1`).
4. Copy the **Salesforce Endpoint Service Name** (it will look similar to `com.amazonaws.vpce.<region>.vpce-svc-xxxxxxxxxxxx`).

## 2. Create the Egress PrivateLink Endpoint in Confluent Cloud

Next, instruct Confluent Cloud to create a secure tunnel to that Salesforce service.

**Dedicated cluster (PrivateLink Access network):**

1. Log in to the Confluent Cloud Console and navigate to your environment.
2. Go to the **Network Management** tab and select the network (Connection type **PrivateLink Access**) where your connectors will run.
3. In the **Egress connections** tab, click **Create endpoint**.
4. Choose the target service, or select **Other** (Salesforce won't be in the curated list), and paste the **Salesforce Endpoint Service Name** ("PrivateLink service name") from Step 1.
5. Give the endpoint a descriptive name; optionally check **Create an endpoint with high availability** (interfaces in multiple AZs).
6. Click **Create**.
7. Once Confluent Cloud provisions the endpoint, it will generate a **VPC Endpoint ID** (e.g., `vpce-0123456789abcdef0`). Copy this ID.

**Enterprise cluster (network gateway):** instead of the above, go to **Network Management → "For serverless products" → your gateway → Access points → Add access point**, then supply the same name / PrivateLink service name / HA option. The generated endpoint ID is used the same way in Step 3.

## 3. Accept the Inbound Connection in Salesforce

Salesforce must explicitly allow the connection coming from your newly created Confluent Cloud VPC Endpoint. (This is the Salesforce-side equivalent of AWS's "accept endpoint connection request" — the service provider accepting the consumer endpoint.)

1. Return to the **Private Connect** page in Salesforce Setup.
2. Click **Create Inbound Connection**.
3. Select **AWS PrivateLink** and click **Next**.
4. Provide a connection name, and in the **VPC Endpoint ID** field, paste the ID you copied from Confluent Cloud.
5. Save the connection. The status will show as "Provisioning" and will eventually transition to **Ready**. (On the Confluent side, the endpoint moves from "Pending accept" to **Ready** once the connection is accepted.)

## 4. Configure DNS Routing in Confluent Cloud (optional but recommended)

This step is **optional** per Confluent's documentation: if you skip it, you must configure the connector to use the **VPC endpoint DNS name** directly as its Salesforce hostname. Creating the DNS record is what lets the connector use its **standard** Salesforce hostname unchanged, so it's recommended for a transparent cutover.

1. **Dedicated:** in Network Management, open the network and click **Create DNS record** in the **DNS** tab (or **Create Record** on the endpoint tile). **Enterprise:** under **"For serverless products" → your gateway → DNS tab → Create DNS record**.
2. Set **Access point** to the Egress PrivateLink Endpoint you created in Step 2.
3. In the **Domain** field, enter the hostname the connector will call. **⚠️ Confirm the exact Salesforce hostname:** Confluent's own examples map the *target service endpoint* hostname, and Salesforce Private Connect may require a **Salesforce-issued private hostname** rather than your public My Domain (`yourcompany.my.salesforce.com`). Verify against Salesforce Private Connect's documentation which hostname resolves over the private path. Do not include `https://` or any trailing path.
4. Click **Save** to finalize the internal DNS mapping.

## 5. Launch the Salesforce Sink Connector

With the infrastructure linked and routing configured, the connector will now use the private path.

1. In Confluent Cloud, deploy your Salesforce sink connector into the same environment and network.
2. In the connector's configuration, use the Salesforce hostname you mapped in Step 4 (see the ⚠️ Confirm note there).
3. Set up your authentication (OAuth or Security Token) as usual.
4. **Choose the connector for your throughput. ⚠️ Confirm against current connector docs** (these connector-specific details could not be re-validated this session): the **Salesforce SObject Sink** and the **Salesforce Bulk API 2.0 Sink** are separate fully-managed connectors — the SObject Sink has no Bulk API option. For high-throughput bulk insertion, deploy the **Salesforce Bulk API 2.0 Sink** connector, which performs insert, update, and delete operations on SObjects using Salesforce Bulk API 2.0. Note that the SObject Sink expects input records structured like Salesforce PushTopic source output, which is a constraint if your topic data did not originate from a Salesforce source connector.

If you created the Step-4 DNS record, connector traffic directed at your Salesforce hostname is routed through the AWS PrivateLink tunnel instead of the public internet; if you skipped it, point the connector's hostname at the VPC endpoint DNS name instead.

## 6. Validate the Private Path

"It works" and "it works privately" look identical from the connector's side — a misconfigured connector will happily succeed over the public internet, so confirm traffic is actually traversing the inbound connection.

1. After all statuses show **Ready** and the connector is running, check the Salesforce **API event logs** (or Login History for the integration user) and confirm the traffic source corresponds to the Private Connect inbound connection rather than a public IP.
2. For hard enforcement, configure Salesforce **API access control** to restrict API traffic for the integration user to the Private Connect connection. Once enforced, any traffic taking the public path fails loudly instead of silently succeeding.
3. Re-run the connector and verify records continue to flow with enforcement enabled. If the connector breaks under enforcement, the DNS record or endpoint configuration is not routing traffic privately — revisit Steps 2–4 before relaxing the restriction.

## 7. Troubleshooting — "Ready" but the connector still can't connect

The endpoint (and Salesforce inbound connection) can reach **Ready** while the connector still fails to connect. The most common cause is a **zonal mismatch**: the target endpoint service's availability zones don't overlap Confluent Cloud's endpoint AZs. Confluent's egress-PrivateLink guide documents this exact symptom, resolved by **enabling cross-zone load balancing** on the endpoint service's load balancer. Because Salesforce owns the endpoint service in this SaaS-provider setup, resolving a persistent zonal mismatch may require **Salesforce-side** configuration (cross-zone load balancing) or ensuring your Confluent network's AZs overlap the region's Salesforce Private Connect AZs. Separately, ensure the endpoint service does not **enforce inbound rules** that would block Confluent's principal.

---

### Validation summary

- **Confirmed against Confluent docs (2026-08-07):** egress PrivateLink for fully-managed connectors; the Dedicated **Egress connections → Create endpoint** and **DNS → Create DNS record** flow; the Enterprise **gateway / Access points** variant; the "Other"/service-name model; the accept-connection handshake; and the cross-zone-load-balancing failure mode.
- **⚠️ Confirm (unverified this session / Salesforce-side):** (1) Salesforce publishing an AWS PrivateLink endpoint service consumable via "Other"; (2) the exact Salesforce hostname to map in the DNS record; (3) the Salesforce SObject Sink vs Bulk API 2.0 Sink specifics and the SObject-Sink-expects-PushTopic-structure constraint (connector docs were unreachable).
- **Corrections applied vs. the original:** network-prerequisite completeness (Dedicated vs Enterprise-gateway vs PNI); the DNS step is optional with a hostname caveat; added the cross-zone-LB / enforce-inbound-rules gotcha as the top "Ready-but-unreachable" cause.
