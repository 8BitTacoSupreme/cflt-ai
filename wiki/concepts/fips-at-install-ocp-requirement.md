---
title: FIPS-at-install OCP Requirement
tags: [linuxone, ibm, s390x, ocp, fips, fsi, compliance, tls, trip-wire]
sources:
  - fsi-dsp://accelerator/confluent-on-linuxone
  - https://docs.confluent.io/platform/current/installation/versions-interoperability.html
  - https://docs.confluent.io/operator/current/co-security-compliance.html
related:
  - patterns/auditor-readonly-rbac-payload-isolation
  - concepts/fsi-compliance
  - patterns/linuxone-on-cfk-reference-architecture
  - concepts/confluent-on-s390x-support-and-ifl-sizing
confidence: high
last_updated: 2026-10-25
last_validated: 2026-10-25
---

# FIPS-at-install OCP Requirement

## Summary

**On LinuxONE (s390x) the question does not arise: Confluent Platform FIPS mode is not yet
supported on s390x** (CP versions-interoperability, "Linux on IBM Z (s390x) support", checked
2026-10-24 against the 8.3 docs). The LinuxONE accelerator's layer 02 therefore does not set
`spec.tls.fips.enabled`, and a tier whose policy requires FIPS 140 validated crypto on the
brokers runs its brokers on x86/ARM until Confluent lists FIPS mode for s390x. mTLS,
TLS 1.2/1.3 and CPACF acceleration are unaffected. See fsi-dsp `KNOWN-GAPS.md` G-02.

The install-time rule below applies to **x86/ARM OCP clusters that run CP FIPS mode**:
`spec.tls.fips.enabled: true` on CFK CRs does **not** make a non-FIPS OpenShift installation
FIPS-compliant. The field is accepted by the CRD (no admission rejection), but CFK's FIPS
support assumes the underlying operating system, the cryptographic providers and the CP
components are all configured for FIPS (CFK security compliance docs), and on OCP the
operating-system part is set only at install time. Red Hat **does not support post-install
FIPS conversion**: OCP must be installed with `fips: true` in `install-config.yaml` from the
start.

This is a silent-failure trip-wire: a green CRD reconcile loop with `fips.enabled: true` on
every CFK component looks correct, but on a non-FIPS OCP cluster the operating-system part of
the requirement is unmet and the deployment fails FSI compliance.

Source of truth: `fsi-dsp://accelerator/confluent-on-linuxone` (layer 02 — `apply_sequence`
`02-tls`) — DESIGN.md layer-02 block (amended 2026-10-24) + KNOWN-GAPS G-02.

## The trip-wire (x86/ARM OCP)

CFK's `spec.tls.fips.enabled: true` turns on CP FIPS mode: the Confluent Platform Java
process runs with the Bouncy Castle FIPS JSSE provider and BCFKS keystores, the only provider
Confluent supports for FIPS (CP security compliance docs). That covers the CP side only; the
CP and CFK docs also require the operating system to be in FIPS mode.

But on a non-FIPS OCP cluster:

- The OS kernel has not been booted with FIPS mode active (`/proc/sys/crypto/fips_enabled = 0`)
- The system OpenSSL providers are not FIPS-validated
- Nothing in the CR or its reconcile checks the node's OS FIPS mode
- The CFK CR shows `fips.enabled: true` → looks correct, is silently non-compliant

**Consequence:** the deployment satisfies CFK's CRD schema, every component reports healthy,
every TLS handshake succeeds — but it does **not** meet the FIPS requirement Confluent
documents (OS, providers and CP all configured for FIPS).
PCI-DSS 4.x §4.2.1, GLBA, and FFIEC encryption controls are not met. A regulator looking at the
cluster will find this on the first sweep, and it's a clean finding (no remediation in place).

## Detection

```bash
# Check that the OCP cluster was installed in FIPS mode
oc get node -o json | jq '.items[0].status.nodeInfo.operatingSystem'

# Verify FIPS is active in the kernel on a worker node
oc debug node/<worker> -- cat /host/proc/sys/crypto/fips_enabled
# Expected: 1
```

If `fips_enabled` returns `0`, **stop**. The cluster is not FIPS-mode and
`spec.tls.fips.enabled: true` will silently fail compliance.

On the LinuxONE accelerator the check runs the other way: `validate-mtls.sh` fails if
`spec.tls.fips.enabled` is set on the Kafka CR, because CP FIPS mode is not yet supported on
s390x.

## Remediation

There is no remediation short of rebuilding the OCP cluster. Red Hat's documented position is
that post-install FIPS conversion is **not supported** — the install-time bootstrap configures
the kernel boot parameters, the OS image, and the OCP control plane components in a FIPS-aware
way that cannot be retrofitted.

**Required action:** reinstall OCP with `install-config.yaml` containing:

```yaml
fips: true
```

This applies to both the bootstrap node and all control-plane / worker nodes.

**Not applicable to LinuxONE:** CP FIPS mode is not yet supported on s390x, so a FIPS-at-install
s390x cluster does not make CP FIPS-compliant. OS/JDK FIPS modes on s390x (RHEL `fips=1`,
IBM Semeru `IBMJCEPlusFIPS`) are outside Confluent's s390x support statement.

## cert-manager

cert-manager Operator for OpenShift (the in-cluster Certificate / Issuer / CA rotation
mechanism wired in by layer 02) is **s390x-supported** (multi-arch images), so certificate
rotation on LinuxONE has no x86 sidecar dependency.

## FSI consequence summary

| Scenario | OS and CP both in FIPS mode | Compliance (FIPS-mandated tier) |
|----------|-----------------------------|---------------------------------|
| x86/ARM OCP installed with `fips: true`, CR sets `spec.tls.fips.enabled: true` | Yes | Met |
| x86/ARM OCP installed without `fips: true`, CR sets `spec.tls.fips.enabled: true` | **No (silent)** | **Failed** |
| x86/ARM OCP installed with `fips: true`, `spec.tls.fips.enabled: false` | No (deliberate) | Failed (deliberate) |
| x86/ARM OCP installed without `fips: true`, `spec.tls.fips.enabled: false` | No | Failed (and explicit) |
| s390x workers (any OCP install) | No — CP FIPS mode not yet supported | Not met by CP; place FIPS-mandated brokers on x86/ARM |

The second row is the only configuration that fails silently and looks correct. mTLS
handshakes succeed either way, so the detection must happen at OCP install time, not at CFK
reconcile time.

## Cross-references

- DESIGN.md layer 02 (mTLS; amended 2026-10-24: no CP FIPS mode on s390x)
- KNOWN-GAPS G-02 — "CP FIPS mode not yet supported on s390x"
- `concepts/confluent-on-s390x-support-and-ifl-sizing` — the s390x support matrix
- `patterns/linuxone-on-cfk-reference-architecture` — layer 02 detail in context
- `concepts/fsi-compliance` — PCI-DSS / GLBA / FFIEC encryption-in-transit framing
- `patterns/auditor-readonly-rbac-payload-isolation` — layer-01 RBAC pattern that
  layer 02 mTLS identifies principals into

## Related

- `patterns/auditor-readonly-rbac-payload-isolation`
- `concepts/fsi-compliance`
- `patterns/linuxone-on-cfk-reference-architecture`
- `concepts/confluent-on-s390x-support-and-ifl-sizing`

## Provenance

- CP versions-interoperability, "Linux on IBM Z (s390x) support" (FIPS mode not yet supported
  on s390x), fetched 2026-10-24; CP security compliance overview (BC-FIPS the only supported
  provider), fetched 2026-10-25; CFK security compliance (FIPS needs the OS, providers and CP
  all configured for FIPS), fetched 2026-10-25
- DESIGN.md layer 02 and KNOWN-GAPS G-02 (fsi-dsp, 2026-10-24 correction)
- Red Hat: FIPS mode is set at OCP install time; post-install conversion is not supported
