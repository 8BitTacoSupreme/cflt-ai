# Original art briefs — the six hand-authored assets

These are the Visio-style prompts that specified ART-1, ART-9, ART-10, ART-13, ART-14 and ART-15
before they were built as vector SVG. **The SVGs in `svg/` are the deliverable** — these briefs
are kept only so the assets can be rebuilt in another tool, restyled for a different brand, or
regenerated at a different aspect ratio.

The ten mermaid assets aren't here; their source is in `mmd/` and in the deck outline itself.

## House style prefix

Paste this ahead of any individual brief below.

> Clean corporate vector illustration, Microsoft Visio / enterprise-architecture-diagram
> aesthetic. Flat design, no gradients, no drop shadows, no 3D. Thin 2px connector lines with
> simple arrowheads. Rounded rectangles for components, cylinders for data stores, hexagons for
> processing. Palette: deep indigo `#173A6C`, Confluent blue `#0074E4`, teal accent `#00A6A0`,
> warm amber `#F2A900` for error/alert paths, neutral grey `#5A6572`, white background.
> Sans-serif labels (Inter or Segoe UI), sentence case, minimal text. Generous whitespace. 16:9.
> No people, no photorealism, no clip-art icons of servers.

---

## ART-1 — Pattern taxonomy grid

A clean 2×2 matrix on a light background. X-axis labeled "Single stream → Multi-stream / joined,"
Y-axis labeled "Stateless → Stateful." Fourteen small rounded-rectangle chips placed across the
quadrants, each with a short label: (bottom-left) Filter, Transform, Route, Split, Share-group
worker; (bottom-right) Static enrich, Claim check; (top-left) Dedup, Windowed aggregate, Retry
ladder; (top-right) Stream–table join, Temporal join, Saga / process manager, Outbox / CDC
ingress. A faint diagonal arrow from bottom-left to top-right annotated "increasing operational
cost." Corporate palette, thin 1pt strokes, no drop shadows, generous whitespace.

*Build note:* the share-group chip is drawn in teal rather than blue, with a footnote reading
"no state, no EOS, no key order — this chip cannot move up or right." That distinction is the
point of the chip, so keep it if you rebuild.

---

## ART-9 — Streaming test pyramid

A five-tier pyramid, widest at the base, on a light background. Tiers bottom-to-top with a label
on the left and a small "cost / runtime" gradient bar on the right that darkens toward the top.
Base: Unit — topology test driver / Flink table tests (annotation: "thousands, milliseconds").
Tier 2: Contract — schema compatibility gate (annotation: "runs on every commit"). Tier 3:
Component — containerized broker + Schema Registry, one handler. Tier 4: Integration — ephemeral
namespaced topics on a real Confluent Cloud environment. Apex: Non-functional — lag, rebalance,
failover, poison pill (annotation: "nightly / pre-release"). To the right of the pyramid, a faded
ghost outline of an hourglass shape labeled "what most teams actually have," with a red X. Flat
design, no bevels or 3D.

*Build note:* a full-size red X over the hourglass fought the shape and read as visual noise. The
built version uses a small red ✕ badge at the hourglass's top-right corner instead, and labels the
three hourglass zones. Leader lines stop at the pyramid edge rather than piercing the tiers.

---

## ART-10 — Environment topology

A layered horizontal architecture diagram, three vertical bands left to right labeled DEV, STAGE,
PROD, each drawn as a rounded container labeled "Confluent Cloud Environment." Inside each: a
Kafka cluster icon, a Schema Registry icon, a Flink compute pool icon, and a small stack of topic
cylinders. A dashed arrow labeled "Cluster Link — masked subset" runs right-to-left from PROD to
STAGE. Below all three bands, a full-width horizontal bar labeled "Terraform (Confluent provider)
— single source of truth" with upward arrows into each environment. Along the top, a thin band
labeled "CI/CD pipeline" with a left-to-right arrow labeled "same artifact, different config."
Private networking indicated by a subtle lock glyph on the PROD band only. Corporate blues and
greys, thin strokes, isometric NOT required — keep it flat and orthogonal.

---

## ART-13 — Maturity model

A horizontal four-segment chevron/arrow ribbon, left to right, each segment a different tint of
the same corporate hue getting progressively darker. Segments labeled 1. Ad hoc, 2. Templated,
3. Governed, 4. Self-service. Under each segment, a small three-line caption block: (1) "Handlers
hand-rolled; DLQs unowned; testing manual." (2) "Golden-path template adopted; schema gate in CI;
DLQ owners named." (3) "All infra as code; contracts enforced; SLOs per handler; canary standard."
(4) "Teams ship handlers without platform involvement; platform owns paved road only." Above the
ribbon, a thin annotation line reading "One change moves a team up one stage — pick it
deliberately." Flat, no gradients inside segments beyond the tint step, plenty of whitespace.

*Build note:* the built version also carries the five scorecard axes (Contract, Error path, Test
depth, Deploy automation, Observability) along the bottom, so S30 needs no second graphic.

---

## ART-14 — The exactly-once boundary

Make the boundary the strongest visual element on the slide; everything else is supporting.

A central shaded region enclosed by a bold dashed boundary, labeled "transactional scope —
exactly_once_v2." Inside the boundary: an input topic cylinder, a processing hexagon, a state
store cylinder, and an output topic cylinder, connected left to right by thin arrows. Outside the
boundary to the right, a separate rounded cloud shape labeled "external system — payment API,
database, notification." A single arrow runs from the processing hexagon out to that cloud and
visibly crosses the dashed boundary; render that one crossing arrow in amber, noticeably thicker
than every other line, with a small label beside it reading "at-least-once, always." No other
amber anywhere in the image.

*Build note:* the label must not sit on top of the crossing point — the crossing is the entire
subject of the image. In the built version the label sits above the boundary with a leader, and
the crossing itself carries a small amber ring plus the caption "the guarantee stops here."

---

## ART-15 — What the diagonal costs

Reuses ART-1's geometry so the audience recognises it instantly as a callback.

Reproduce the same 2×2 matrix geometry as the pattern taxonomy grid — X-axis "Single stream →
Multi-stream / joined," Y-axis "Stateless → Stateful" — but with the pattern chips faded to light
grey. Overlay the bottom-left-to-top-right diagonal as a prominent thickening wedge, narrow at
bottom-left and wide at top-right. Along the wedge, four small labeled markers stacked as the
wedge widens, reading in order: "partitions," "state size," "retention," "egress." At the narrow
end, a caption "parallelism × throughput, nothing else." At the wide end, a caption "state +
joins + timers + a compensating path." No currency symbols, no numbers anywhere in the image.
