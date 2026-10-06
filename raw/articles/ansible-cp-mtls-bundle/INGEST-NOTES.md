---
title: ansible-cp-mtls-bundle — Ingest Notes
parked_on: 2026-05-27
status: parked-as-companion (NOT for fsi-dsp import)
companion_to:
  - wiki/patterns/cp-mtls-self-signed-setup.md
  - wiki/patterns/cp-tls-debugging-by-component.md
  - wiki/concepts/linuxone-jdk-tls-gotchas.md
---

# ansible-cp-mtls-bundle — Why This Lives Here, Not in fsi-dsp

## TL;DR

This is a standalone Ansible playbook bundle that automates §1–§6 of the
[CP mTLS self-signed setup pattern](../../../wiki/patterns/cp-mtls-self-signed-setup.md).
It was evaluated for inclusion in `fsi-dsp/ansible/` on 2026-05-27 and
**declined** — fsi-dsp already has a strictly more comprehensive `cp_mtls`
role. The bundle is parked here as a portable companion artifact for
readers outside the fsi-dsp scenario harness.

## Evaluation Result (2026-05-27)

`fsi-dsp/ansible/roles/cp_mtls/` is strictly better than this bundle on
every axis:

| Surface | Bundle | fsi-dsp `cp_mtls` |
|---|---|---|
| CA / broker / client / truststore / ssl_config tasks | yes | yes |
| **PKCS#11 / CEX HSM mode** | no (acknowledged gap) | yes (`tasks/pkcs11.yml` + `templates/java.security.pkcs11.j2`) |
| **Molecule tests** (project convention) | no | yes |
| Variable namespacing | `kafka_*` (out of convention) | `cp_mtls_*` (matches `cp_topic`, `cp_rbac`, `cp_schema`) |
| Role structure | 5 split roles, unprefixed | Single `cp_mtls` role with `tasks/<stage>.yml` |
| Site integration | Standalone | Wired into `site.yml` via `cp-rhel` scenario |
| Assert preflight + result counters + fail handler | no | yes |
| KRaft authorizer + principal mapping + super.users derivation | hard-coded vars | derived from `groups['kafka_brokers']` with override |

The two `ssl-block.properties.j2` templates are functionally identical
(same property names, same KRaft `StandardAuthorizer`, same TLS pin) —
diff is mechanical (var names + PKCS11 branch).

`fsi-dsp/scenarios/cp-rhel-linuxone/playbooks/verify-mtls.yml` also covers
the bundle's `99-verify-mtls.yml` more cleanly (Ansible-native temp-file
lifecycle, `openssl s_client -brief -verify_return_error`, `cp_mtls_*` var
namespace).

## Who Is This Bundle For

Someone outside the fsi-dsp harness who wants to stand up CP mTLS without
the fsi-dsp scenario harness. The bundle is well-scoped, has working
`community.crypto` roles, and maps 1:1 to §1–§6 of the source runbook —
making it a clean companion to the wiki pattern for portable distribution.

## Layout

```
ansible-cp-mtls-bundle/
├── bundle-README.md            ← author's original README (was alongside the bundle)
├── INGEST-NOTES.md             ← this file
└── ansible-mtls/               ← the bundle itself
    ├── README.md
    ├── ansible.cfg
    ├── requirements.yml
    ├── site.yml
    ├── inventory/hosts.yml.example
    ├── group_vars/{all.yml, vault.yml.example}
    ├── playbooks/01..99-*.yml
    ├── roles/{kafka_ca, kafka_broker_cert, kafka_client_cert, kafka_truststore, kafka_ssl_config}/
    └── files/{csrs, signed, clients}/.gitkeep
```

## Do Not

- **Do not** import this into `fsi-dsp/ansible/`. It would create a parallel
  mTLS role to `cp_mtls`, which is strictly worse than the current state.
- **Do not** ingest this into the wiki as a separate article — it's parked
  here as a raw companion artifact for downstream users; the wiki coverage
  is already complete via `cp-mtls-self-signed-setup`,
  `cp-tls-debugging-by-component`, and `linuxone-jdk-tls-gotchas`.

## Cross-References

- Wiki pattern (canonical procedure): [`wiki/patterns/cp-mtls-self-signed-setup.md`](../../../wiki/patterns/cp-mtls-self-signed-setup.md)
- Wiki pattern (debug recipes): [`wiki/patterns/cp-tls-debugging-by-component.md`](../../../wiki/patterns/cp-tls-debugging-by-component.md)
- Wiki concept (LinuxONE gotchas): [`wiki/concepts/linuxone-jdk-tls-gotchas.md`](../../../wiki/concepts/linuxone-jdk-tls-gotchas.md)
- fsi-dsp canonical role: `raw/repos/fsi-dsp/ansible/roles/cp_mtls/` (the one to actually use inside the fsi-dsp harness)
- fsi-dsp live-cluster verify: `raw/repos/fsi-dsp/scenarios/cp-rhel-linuxone/playbooks/verify-mtls.yml`
