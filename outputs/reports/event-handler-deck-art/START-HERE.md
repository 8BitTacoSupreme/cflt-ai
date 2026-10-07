# Handoff brief — build the deck

**Deliverable:** a 31-slide presentation, *Event Handler Design Patterns on Confluent Cloud —
A practice playbook for building, proving, and shipping real-time data services.*

**Audience:** platform engineering leads and application architects at an enterprise (financial
services). Technical, senior, impatient. They have shipped Kafka before. No introductory framing,
no "what is a topic" slides.

**Runtime:** 40–46 minutes presented, Q&A separate.

---

## What's in this package

```
START-HERE.md         you are here
deck-outline.md       the full 31-slide outline — content source of truth
contact-sheet.html    open this first; every graphic rendered, in slide order
art/svg/              16 finished graphics — USE THESE
art/png/              1600×900 rasters, reference only, do not place in slides
art/mmd/              mermaid source for the 10 diagram assets, if edits are needed
art/ART-BRIEFS.md     original design briefs for the 6 hand-authored assets
```

Open `contact-sheet.html` in a browser before anything else. It shows all sixteen graphics in
slide order with a note on each.

---

## The one thing to get right

This deck argues that **streaming projects fail in the handler, not the broker.** Every slide
serves that. Slide 2 names six recurring failures and each one is answered by a specific later
slide — that promise is the deck's spine, so the six-item list on S2 and its callbacks must stay
intact and legible.

Four slides carry the most weight and deserve the most design attention:

| Slide | Why |
|---|---|
| **S7** — Delivery semantics | Two graphics (ART-3 + ART-14). The exactly-once boundary is the single idea people leave with. |
| **S15** — Error taxonomy & retry ladder | The most-referenced slide in the deck. Three error classes must be instantly distinguishable. |
| **S25** — The pipeline | Carries a deliberate caveat: the schema gate catches syntax, not meaning. Don't let design flatten that nuance into a triumphant checkmark. |
| **S27** — What you can't undo | The best slide in the deck. Reversible vs. irreversible-ish. Two columns, high contrast, no decoration. |

---

## Art placement

Sixteen graphics across fourteen slides. S7 takes two.

| Slide | Asset | Aspect | Placement |
|---|---|---|---|
| S4 | `art-01-pattern-taxonomy.svg` | 16:9 | Full bleed or near-full |
| S5 | `art-02-handler-anatomy.svg` | wide | Full width, upper two-thirds |
| S7 | `art-03-delivery-semantics.svg` | **portrait** | Right half, full height |
| S7 | `art-14-eos-boundary.svg` | 16:9 | Its own slide or the S7 build's second beat |
| S12 | `art-15-cost-diagonal.svg` | 16:9 | Full bleed — it's a callback to S4, so match S4's framing |
| S13 | `art-04-saga.svg` | **portrait** | Right half, full height |
| S14 | `art-05-request-reply.svg` | wide | Full width |
| S15 | `art-06-retry-ladder.svg` | **wide, short** | Full slide width, ~⅓ height. Lots of headroom for the bullets. |
| S17 | `art-07-claim-check.svg` | wide | Full width |
| S18 | `art-08-outbox-cdc.svg` | wide | Full width |
| S21 | `art-09-test-pyramid.svg` | 16:9 | Full bleed |
| S24 | `art-10-environment-topology.svg` | 16:9 | Full bleed |
| S25 | `art-11-cicd-schema-gate.svg` | wide | Full width, lower half |
| S26 | `art-12-blue-green.svg` | wide | Full width |
| S29 | `art-16-handler-dr.svg` | wide | Full width |
| S30 | `art-13-maturity-model.svg` | 16:9 | Full bleed — already includes the scorecard axes |

Slides with no graphic are deliberate: S2, S3, S6, S8, S9, S10, S11, S16, S19, S20, S22, S23,
S27, S28, S31. S3 and S20 carry tables; S27 wants a strong two-column typographic treatment.

---

## Rules for the art

1. **Place the SVGs, don't rebuild them.** They're vector; scale freely. Text stays selectable.
2. **Don't recolor.** The palette is load-bearing:

   | Role | Hex |
   |---|---|
   | Primary / text | `#173A6C` |
   | Accent | `#0074E4` |
   | Secondary accent | `#00A6A0` |
   | Error paths **only** | `#F2A900` (fill `#FDF3DC`) |
   | Neutral text | `#5A6572` |
   | Surfaces | `#EAF1FA`, `#E3F5F4`, `#F4F6F8` |

   Amber appears rarely on purpose. The single crossing arrow on ART-14 and the DLQ nodes rely on
   amber meaning "this is the thing that bites you." If amber gets used for slide furniture,
   headers, or bullets, those graphics stop working. Pick slide chrome from the neutrals.
3. **Light slides.** The art is drawn for a light ground. A dark deck would need every asset
   rebuilt — flag it rather than inverting them.
4. **Three assets have specific geometry that shouldn't be cropped:**
   - ART-14 — the dashed boundary and the amber arrow crossing it. The crossing point is the
     subject; don't crop or cover it.
   - ART-15 — reproduces ART-1's grid geometry deliberately, as a visual callback. Frame S12 the
     same way as S4 so the rhyme lands.
   - ART-9 — the ghost hourglass to the right of the pyramid is part of the argument, not a
     decorative element. Keep it.
5. **Editing a mermaid diagram:** edit `art/mmd/<name>.mmd`, then `bash build.sh` in the art
   directory. Don't hand-edit the generated SVG — it'll be overwritten.

---

## Typography

The graphics use Inter (falling back to Segoe UI / system sans). Match or complement it in the
slide master. If you substitute, pick something with the same skeleton — a neutral grotesque —
so the labels inside the art don't fight the slide type. Avoid anything with strong personality;
the content is dense and the type's job is to stay out of the way.

Tabular figures wherever numbers align (the config table on S18, the scorecard on S30).

---

## Three open items — carried, not resolved

These are content gaps, flagged so nobody designs around them assuming they're settled:

1. **S17** wants the real max message size for the target cluster type printed beside the claim
   check graphic. It could not be confirmed from Confluent's Cloud quotas documentation. Either
   the author supplies it or the slide ships without a number.
2. **Act 5 (S21–S23, testing)** is the least source-backed part of the deck.
3. The topic-naming convention on **S20** was corrected to match the CI-enforced canon
   (`{domain}.{application}.{version}.{entity}`). If any other slide or asset shows a topic name,
   it must use that ordering.
