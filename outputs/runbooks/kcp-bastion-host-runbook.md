---
title: KCP Bastion Host Setup
subtitle: Stand up a disposable, pre-installed bastion host with KCP (Copy Paste)
audience: Platform / infra engineers who need quick jump-host access into a private VPC
validated: 2026-09-16 against confluentinc/kcp README (install script, create-asset bastion-host flags)
confidence: medium
related-canon: wiki/patterns/kcp-msk-migration-bastion-host.md
---

# KCP Bastion Host Setup

**Purpose:** Stand up a disposable EC2 bastion inside a target VPC in minutes, using KCP
(Copy Paste) to generate the Terraform — pre-installed with Terraform, Confluent CLI, and Kafka
CLI, with no hand-provisioning required.

---

## 0. Install the KCP CLI

Run this wherever you'll launch `kcp create-asset` from — your laptop, or an existing jump host
already inside the target VPC (two-hop pattern, see below).

```bash
curl -fsSL https://raw.githubusercontent.com/confluentinc/kcp/main/install.sh | sh
kcp version
```

Pin a specific version instead of latest if you want reproducibility:

```bash
curl -fsSL https://raw.githubusercontent.com/confluentinc/kcp/main/install.sh | KCP_VERSION=v0.8.5 sh
```

Per KCP's own README: don't build from source for normal use — only released binaries (source
builds carry untested breaking changes).

## 1. Provision the bastion via KCP

```bash
kcp create-asset bastion-host \
  --region <region> \
  --vpc-id <vpc-id> \
  --bastion-host-cidr 10.0.255.0/24 \
  --existing-internet-gateway \
  --output-dir bastion_host

cd bastion_host && terraform init && terraform apply
terraform output   # bastion_host_public_ip
```

This provisions an Amazon Linux 2023 EC2 with **KCP + Terraform + Confluent CLI + Kafka CLI
already installed** — nothing extra to install on the host itself.

`--existing-internet-gateway` should be passed for essentially every real VPC — omitting it on a
VPC that already has an IGW attached fails the apply. Pass `--security-group-ids <existing-sg-id>`
instead of letting KCP create its own SG if you want to reuse an already-approved one.

### Two-hop pattern (jump host already exists)

If a jump host already exists in the target VPC, install the `kcp` binary there first (step 0),
then run `kcp create-asset bastion-host` **from** that jump host to get a clean, dedicated,
pre-installed migration EC2 — instead of hand-installing Terraform/Confluent CLI/Kafka CLI onto
the existing host directly. SSH to the new bastion happens from the jump host, so port 22 never
needs to be opened externally.

## 2. Access rules — pick one

### A. Plain SSH, scoped to your IP
- VPC has an Internet Gateway attached
- Bastion's subnet route table: `0.0.0.0/0 → igw-xxxxx`
- Bastion has a public IP (KCP's generated subnet auto-assigns one)
- Security group inbound: TCP 22 from `<your-ip>/32` only — never `0.0.0.0/0`
- Custom NACL, if one's attached to the subnet: inbound allow 22 from your IP, outbound allow
  ephemeral ports 1024–65535 back to your IP

### B. EC2 Instance Connect (KCP's actual default)
- Security group inbound: TCP 22 scoped to the AWS EC2 Instance Connect IP range for your
  region — KCP fetches this live from `ip-ranges.amazonaws.com` and applies it automatically if
  you let it generate its own security group
- Connect:
  ```bash
  aws ec2-instance-connect ssh --instance-id <instance-id> --region <region>
  ```
  or the **Connect** button in the EC2 console
- Needs: instance has a public IP; your IAM principal has
  `ec2-instance-connect:SendSSHPublicKey` + `ec2:DescribeInstances`

### C. SSM Session Manager — no inbound port at all
- No security group inbound rule needed whatsoever
- Attach `AmazonSSMManagedInstanceCore` to the bastion's instance profile (KCP never attaches an
  IAM role for you — manual step regardless of access method)
- SSM Agent is pre-installed on the Amazon Linux 2023 AMI KCP uses
- Security group only needs **outbound** 443 (to the regional SSM endpoints — works over an
  existing NAT/IGW route, or SSM VPC interface endpoints if the subnet has no internet route at
  all)
- Connect:
  ```bash
  aws ssm start-session --target <instance-id> --region <region>
  ```

Recommended default: **C**. It doesn't depend on the subnet having a public IP or any open
inbound port, at the cost of one IAM role attachment.

## 3. Cleanup

- Detach/delete the IAM role + instance profile attached in step 2
- `terraform destroy` in `bastion_host/`

## Caveats

- KCP never attaches an IAM role/instance profile to the bastion for you — that's always a
  manual step before running any command that needs AWS permissions from the host.
- KCP's own default-generated bastion IAM role (if you go on to attach one for migration work)
  is broad (`PowerUserAccess` + self-service IAM management) — tighten it to the minimum your
  use case needs.
- `--existing-internet-gateway` should be passed for essentially every real VPC; omitting it on a
  VPC that already has an IGW fails the apply.

## Related

- [wiki/patterns/kcp-msk-migration-bastion-host.md](../../wiki/patterns/kcp-msk-migration-bastion-host.md) —
  full KCP bastion-host pattern, IAM policy tiers, and the broader MSK migration pipeline this
  bastion feeds into when used for migration rather than standalone access
