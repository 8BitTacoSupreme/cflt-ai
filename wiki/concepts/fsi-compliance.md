---
title: FSI Compliance
tags: [fsi compliance audit ci-cd governance]
sources: [fsi-dsp://script/validate-fips, fsi-dsp://adr/006]
related: [concepts/fsi-data-streaming-platform, concepts/sla-tiers, patterns/fsi-governance-automation, concepts/schema-evolution-strategies]
confidence: high
last_updated: 2026-04-11
last_validated: 2026-10-25
---

# FSI Compliance

## Summary

The FSI Kafka Platform CI/CD workflow provides a complete audit trail from PR creation through deployment and post-apply validation. Every infrastructure change is traceable: change request (PR), automated validation (CI), segregation of duties (non-author reviewer), approval gate (branch protection), deployment (Terraform apply), and verification (post-apply checks). The compliance guide maps each step to generic FSI control categories translatable to OCC/FFIEC, PRA, MAS, APRA, and OSFI frameworks.

## Detail

### Audit Trail Flow

```
PR Created → CI Validation → Human Review → Merge to Main → Terraform Apply → Post-Apply Validation
     |              |               |               |                |                    |
Change request  Automated      Segregation     Approval         Infrastructure       Verification
                checks         of duties       gate             deployment
```

Each step produces evidence in GitHub (PR page, Actions job, review tab, job summary).

### Control Mapping

| Control Category | Workflow Step | Evidence Location |
|-----------------|--------------|-------------------|
| Change Management | PR created with template | GitHub PR page — completed checklist, description |
| Automated Validation | CI lint + validate + plan | GitHub Actions "Lint & Validate" job |
| Schema Governance | Schema compatibility check | GitHub Actions "Lint & Validate" job |
| Override Documentation | Compatibility override check | GitHub Actions "Lint & Validate" job |
| Access Control Review | PR template checkboxes | PR page — RBAC verified, data classification reviewed |
| Segregation of Duties | Non-author reviewer approval | PR review tab |
| Approval Gate | Branch protection merge | PR merge event — required reviewers met, CI passed |
| Deployment Automation | Terraform apply | GitHub Actions "Terraform Apply" job |
| Post-Deploy Verification | Post-apply validation | Job summary "Compliance Audit Trail" |
| Audit Logging | Job summary + annotations | Workflow run page — timestamp, actor, SHA, run ID |

### Navigating an Audit

1. Start at the GitHub repository Pull Requests tab (filter: Merged)
2. Find the PR by topic name, date, or author
3. Review PR description and compliance checklist completion
4. Check "Files changed" for Terraform/schema/config modifications
5. Check "Conversation" tab for at least one non-author approving review
6. Click CI check link to view workflow run in GitHub Actions
7. Open "Lint & Validate" job — format checks, schema validation, compatibility, override detection
8. Open "Terraform Apply" job — infrastructure deployment
9. Review "Compliance Audit Trail" job summary — scenario, timestamp, actor, SHA, run ID, validations
10. Verify all validation checks show PASS

### Evidence Checklist for Examiners

- PR created with completed checklist (change management)
- CI checks passed (automated validation)
- At least one non-author reviewer approved (segregation of duties)
- Branch protection rules enforced (approval gate)
- Terraform apply succeeded (deployment automation)
- Post-apply validation PASSED (post-deploy verification)
- Job summary contains timestamp, actor, commit SHA (audit logging)

### Regulatory Framework Mapping

Generic control categories map to specific frameworks:

| Framework | Region | Key Mapping |
|-----------|--------|-------------|
| OCC/FFIEC | United States | Change Management → IT Handbook - Dev & Acquisition; Access Control → IT Handbook - InfoSec; Audit → IT Handbook - Audit |
| PRA | United Kingdom | SS1/21 Operational Resilience; outsourcing and third-party risk management |
| MAS TRM | Singapore | Section 6 (IT Project Management), Section 7 (System Development) |
| APRA CPS 234 | Australia | Paragraph 27 (access controls), Information Security |
| OSFI B-13 | Canada | Technology and Cyber Risk Management; change management domain |

Each institution should maintain a cross-reference document mapping these categories to their internal control IDs.

### Key Terms

- **SLA Tier** — classification (critical, standard, best-effort, compliance) determining topic config defaults
- **Data Classification** — sensitivity categorization: confidential (PII, financial), internal, public
- **CSFLE** — Client-Side Field-Level Encryption for individual Kafka message fields
- **C4E** — Cloud Center of Excellence; review body for governance overrides

## Related

- [FSI Data Streaming Platform](concepts/fsi-data-streaming-platform.md) — platform overview
- [Governance Automation](patterns/fsi-governance-automation.md) — the CI/CD pattern producing this audit trail
- [SLA Tiers](concepts/sla-tiers.md) — tier definitions
- [Schema Evolution Strategies](concepts/schema-evolution-strategies.md) — schema governance enforced by CI
