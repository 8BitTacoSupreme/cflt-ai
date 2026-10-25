---
id: linuxone-fips-gap-g02-cross-cutting-110
query: "Why is FIPS-at-install required for the LinuxONE accelerator's TLS layer?"
expected_route: wiki+mcp
floor_model: haiku
tags: [fips, ocp, linuxone, gap-g02, trip-wire, cross-cutting, wiki-05, premise-correction, s390x]
required_claims:
  - "G-02"
  - "fips-at-install-ocp-requirement"
  - "not yet supported on s390x"
  - "x86"
forbidden_claims:
  - "I cannot help"
  - "no information"
  - "FIPS-at-install is required for the LinuxONE accelerator"
---

## Case: FIPS-at-install gap G-02 — cross-cutting (WIKI-05), premise correction

The query's premise is wrong since 2026-10-24: the LinuxONE accelerator's TLS layer does not
set CP FIPS mode, because Confluent Platform FIPS mode is not yet supported on s390x.

**What the answer MUST contain:**
- Correction of the premise: layer 02 does not set `spec.tls.fips.enabled`
- Reference to KNOWN-GAPS G-02, now "CP FIPS mode not yet supported on s390x"
- Citation of wiki/concepts/fips-at-install-ocp-requirement.md
- FIPS-mandated broker tiers run on x86/ARM, where the OCP FIPS-at-install rule
  (`fips: true` in install-config.yaml) applies

**What the answer MUST NOT contain:**
- Refusal to answer the FIPS question
- A claim that FIPS-at-install makes CP FIPS-compliant on LinuxONE
- Suggestion that post-install FIPS conversion is a supported Red Hat path

**Negative-space trigger:** NO
