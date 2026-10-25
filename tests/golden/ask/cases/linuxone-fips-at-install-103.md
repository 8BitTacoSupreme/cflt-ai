---
id: linuxone-fips-at-install-103
query: "Why does spec.tls.fips.enabled have no effect on my OCP cluster?"
expected_route: wiki+mcp
floor_model: haiku
tags: [fips, ocp, linuxone, gap-g02, wiki-04, s390x]
required_claims:
  - "fips-at-install-ocp-requirement"
  - "post-install"
  - "not yet supported on s390x"
  - "install-config.yaml"
forbidden_claims:
  - "I cannot help"
  - "no information"
---

## Case: FIPS-at-install OCP requirement (WIKI-04, gap G-02)

**What the answer MUST contain:**
- Citation of wiki/concepts/fips-at-install-ocp-requirement.md
- Explanation that `spec.tls.fips.enabled` does not make a non-FIPS OCP install FIPS-compliant (silent: the OS part of the requirement is unmet)
- Red Hat does not support post-install FIPS conversion — must be set in install-config.yaml at install time

**What the answer MUST NOT contain:**
- Refusal to answer the FIPS question
- Suggestion that post-install FIPS conversion is supported

**Negative-space trigger:** NO
