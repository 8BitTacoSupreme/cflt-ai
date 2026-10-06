---
title: LinuxONE JDK / TLS / s390x Gotchas
tags: [linuxone, ibm, s390x, ibm-semeru, openj9, fips, pkcs12, pkcs11, cex, tls, ssl, jdk, rocksdb, fsi]
sources:
  - "internal field notes (mTLS on CP / LinuxONE)"
related:
  - patterns/cp-mtls-self-signed-setup
  - patterns/cp-tls-debugging-by-component
  - concepts/fips-at-install-ocp-requirement
  - concepts/linuxone-platform-foundations
  - concepts/linuxone-kafka-integration
  - concepts/s390x-custom-image-build-pipeline
  - patterns/linuxone-kafka-tuning
confidence: medium
last_updated: 2026-05-27
last_validated: 2026-05-27
---

# LinuxONE JDK / TLS / s390x Gotchas

## Summary

Companion reference for the LinuxONE / IBM Semeru / FIPS-specific failure modes that come up running Confluent Platform on s390x. Pulled out of the mTLS setup runbook so the canonical procedure stays clean and the L1 quirks are searchable on their own. Two sections: (1) SSL / JDK-related — the differences between IBM Semeru and OpenJDK on x86 that silently change TLS behavior; (2) non-SSL s390x hurdles — multi-arch image gaps, RocksDB JNI, connector compatibility, endianness.

## Detail

### SSL / JDK-Related

#### IBM JDK crypto provider order

On IBM Semeru / OpenJ9, the default provider order has **IBMJCE first and IBMJSSE2 handling TLS** — not SunJCE / SunJSSE. Cipher suite names sometimes differ, the default enabled cipher list is narrower, and configs that work on Temurin/OpenJDK on x86 can silently pick different defaults. If someone edited `java.security` to prefer SunJCE on a Semeru host, PKCS12 loading gets weird in non-obvious ways.

**First diagnostic:**

```bash
java -XshowSettings:properties 2>&1 | grep security.provider
```

That confirms what's actually loaded. Pair it with `-Djavax.net.debug=ssl:handshake:verbose` — the ClientHello vs ServerHello cipher lists expose provider-order issues immediately.

> ⚠️ unverified — exact IBMJCE / IBMJSSE2 ordering as the Semeru default; this is IBM JDK documentation territory, not Confluent docs. The behavioral claim (IBM JDK ships with non-Sun providers as the defaults and TLS handshake behavior differs from OpenJDK Temurin) is well-established operational knowledge on IBM Z.

#### FIPS mode

Regulated-FSI L1 LPARs almost certainly have `fips=1` at the OS level and probably FIPS enabled at the JDK level too. This:

- Eliminates non-approved cipher suites
- Blocks MD5 and some SHA-1 uses
- Forces specific key lengths
- Can reject keystores generated with non-FIPS-approved algorithms

PKCS12 keystores created with `keytool` on a non-FIPS box sometimes fail to load on a FIPS L1 host because of the **MAC algorithm**. The fix is to **generate the keystore on the FIPS host** with the right MAC algorithm flags.

**Check FIPS state:**

```bash
cat /proc/sys/crypto/fips_enabled        # 1 = OS FIPS on
java -XshowSettings:properties 2>&1 | grep -i fips
```

If the OCP cluster itself wasn't installed in FIPS mode, the CFK `spec.tls.fips.enabled: true` field is a no-op — see [fips-at-install-ocp-requirement](fips-at-install-ocp-requirement.md). FIPS is install-time on OCP; you can't bolt it on later.

#### PKCS12 MAC algorithm

Older `keytool` defaults to `HmacPBESHA1` for the MAC; FIPS may require SHA-256. Force it:

```bash
keytool ... \
  -J-Dkeystore.pkcs12.macAlgorithm=HmacPBESHA256 \
  -J-Dkeystore.pkcs12.macIterationCount=100000
```

This is the single most common reason a keystore generated on a developer laptop won't load on an L1 broker. JKS is deprecated and travels even worse than PKCS12 — don't fall back to JKS to dodge this; fix the MAC algorithm.

#### Cipher suite intersection

If x86 clients talk to s390x brokers and the handshake fails with "no cipher suites in common," dump enabled suites on each side and look at the intersection. The IBM JDK's enabled-by-default set is narrower; under FIPS it's narrower still. Sometimes pinning `ssl.cipher.suites` on both sides is the fastest fix — pick a small intersection that both honor and lock it in.

#### TLS 1.3 edge cases on older Semeru

IBM JDK's TLS 1.3 behavior has had quirks around session resumption and some curve negotiations. If nothing else makes sense, force `ssl.enabled.protocols=TLSv1.2` as a **diagnostic** (not a fix) to confirm whether 1.3 is the culprit — then **patch the JDK, not the config**. Pinning the cluster to TLS 1.2 long-term burns a regulator question for no reason.

#### PKCS#11 / Crypto Express (CEX) cards

If they're backing private keys with **Crypto Express cards via PKCS#11**, the wiring is:

- Add a PKCS#11 provider entry to `java.security`
- Reference the slot via `NONE` in `ssl.keystore.location`
- Set `ssl.keystore.type=PKCS11`

The CEX configuration matters: cards run in either **CCA** or **EP11** mode, and which mode the workload talks to is configured at the LPAR / TKE layer. First-pass CP deployments usually shouldn't touch this — get software keys working first, then swap to HSM-backed. If you're trying to use HSM-backed keys out of the gate, that's likely where you're stuck.

> ⚠️ unverified — exact PKCS#11 wiring syntax (the `NONE` placeholder, provider naming) is JDK-vendor and JCA-spec territory rather than Confluent docs. The architectural shape (PKCS#11 provider → CEX card → CCA/EP11 mode) is canonical on IBM Z but the precise property names should be re-checked against the target JDK's PKCS#11 guide before production use.

#### Time skew

LPAR time drift vs client time > a few minutes will cause "certificate not yet valid" failures during the handshake. STP is the canonical solution on IBM Z (see [linuxone-platform-foundations](linuxone-platform-foundations.md)); for off-frame clients, NTP. Verify before you debug ciphers.

#### Hostname resolution

The SAN must match what the client dials. If the client connects by IP but the cert only lists DNS names, `ssl.endpoint.identification.algorithm=HTTPS` will fail the handshake. Either add IP SANs at cert-mint time or always connect by name.

### Non-SSL s390x Hurdles

Broader rough edges seen tripping up CP deployments on LinuxONE — these aren't TLS-specific but tend to show up together, often within the same day as the mTLS work.

#### Confluent image / sidecar architecture

Confluent's official images are multi-arch, but some sidecars (monitoring agents, custom connectors, log shippers) only ship x86 and will run under **QEMU emulation without anyone noticing** — until throughput numbers come in 10× below expectations. Always confirm the manifest of every image in the pod's containers list returns an `s390x` digest:

```bash
docker manifest inspect <image>:<tag> | grep -A2 'architecture'
```

For Confluent images that don't have an s390x build, build your own — see [s390x-custom-image-build-pipeline](s390x-custom-image-build-pipeline.md).

#### RocksDB native libraries for Kafka Streams on s390x

Historically the Achilles heel of Streams workloads on Z. Verify the RocksDB JNI binary inside the Streams jar includes a `linux-s390x` variant, or supply one. If the binary isn't there, the application throws at startup with a `UnsatisfiedLinkError` referencing RocksDB.

#### Connector JAR compatibility

Most pure-Java connectors work fine on s390x. Anything with **JNI** (certain JDBC drivers, native compression libs, some proprietary source/sink connectors) needs s390x builds — confirm before committing to the architecture in a design doc. Common offenders: Oracle JDBC thin-client native bits, vendor-specific source connectors shipping with bundled native crypto, and any connector that bundles its own compression codec.

#### Endianness in custom serializers

Any hand-rolled serializer that does manual `ByteBuffer` manipulation with assumed little-endian layout will break on s390x (which is big-endian). Rare, but expensive when it happens. **Avro, Protobuf, JSON Schema are all fine** — they don't assume an endianness. This is one more reason to ban hand-rolled binary serializers in the FSI canon.

## Related

- [CP mTLS Self-Signed Setup](../patterns/cp-mtls-self-signed-setup.md) — the canonical mTLS procedure this article supports
- [CP TLS Debugging by Component](../patterns/cp-tls-debugging-by-component.md) — handshake debug recipes per component
- [FIPS-at-install OCP Requirement](fips-at-install-ocp-requirement.md) — silent-failure trip-wire on non-FIPS OCP
- [LinuxONE Platform Foundations](linuxone-platform-foundations.md) — STP, UKO, CBU, SMC-R foundations
- [LinuxONE Kafka Integration](linuxone-kafka-integration.md) — z/OS bridge and platform positioning
- [s390x Custom Image Build Pipeline](s390x-custom-image-build-pipeline.md) — `docker buildx --platform linux/s390x` for closing image gaps
- [LinuxONE Kafka Tuning](../patterns/linuxone-kafka-tuning.md) — Kafka 4.2 / CP 8.2 tuning with FSI tier overlay

---

*MCP routing for this article: most claims are IBM-JDK / FIPS / s390x territory rather than Confluent product surface, so `confluent-docs` MCP is not the primary validator. Source is the upstream LinuxONE mTLS runbook, cross-referenced against the validated `fips-at-install-ocp-requirement` and `linuxone-platform-foundations` articles already in the wiki. Three ⚠️ unverified markers retained on: (1) IBMJCE / IBMJSSE2 default ordering on Semeru, (2) exact PKCS#11 + CEX wiring syntax, and (3) the IBM JDK TLS 1.3 quirks (operationally reported but not pinned to a specific JDK version here). confidence: medium pending a dedicated IBM-docs revalidation pass.*
