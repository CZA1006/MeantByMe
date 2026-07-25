# MeantByMe — visual identity

Slogans, verbatim:

| | |
|---|---|
| 中文 | 意由我 — **让话说完，让我做主** |
| English | MeantByMe — **Completed with AI. Meant by me.** |

Both say the same two things in the same order: the sentence gets finished, and
the patient is the one who decides. Every part of the identity below encodes
that pair.

## The mark

Two corner brackets and a check.

The brackets are the CJK quotation pair 「 」 — what someone said, held intact
(让话说完). They sit 180° apart so they frame without closing: the sentence is
bracketed, not boxed in. The check is the authorization (让我做主), drawn a
little heavier than the frame because it is the part that matters, and carrying
the violet this product reserves for the private confirmation moment.

The two-tone split is load-bearing. Teal is the system holding the words;
violet is the patient approving them. Never recolour the check to teal — that
collapses the whole idea into a generic "verified" badge.

| File | Use |
|---|---|
| `logo-mark.svg` | Primary mark, two-tone. Anything ≥ 20px. |
| `logo-mark-dark.svg` | Brighter two-tone mark for dark system surfaces. |
| `logo-mark-mono.svg` | Single colour, inherits `currentColor`. For dark or coloured grounds. |
| `favicon.svg` · `favicon-32.png` | Small-size cut: the brackets stop resolving below ~20px, so the check carries the brand alone on a teal tile. |
| `app-icon.svg` · `app-icon-192.png` · `app-icon-512.png` · `apple-touch-icon-180.png` | Home-screen tile. Warm paper ground, not a saturated fill — this is a calm, light product, and a cream tile also reads distinctly on a home screen of dark icons. |
| `logo-lockup-zh.svg` · `.png` | Horizontal lockup, Chinese. |
| `logo-lockup-en.svg` · `.png` | Horizontal lockup, English. |
| `logo-lockup-zh-dark.svg` · `.png` | Chinese lockup for the dark launch screen. |
| `logo-lockup-en-dark.svg` · `.png` | English lockup for the dark launch screen. |

Clear space is 6 units of the mark's 48-unit grid — one bracket stroke — on
every side. The lockup SVGs use live text, so they need the type stack
installed; use the exported PNGs anywhere fonts are not guaranteed.

The header in `index.html` links `logo-mark.svg` directly and swaps to
`logo-mark-dark.svg` with the selected appearance. The launch transition uses
the corresponding raster lockup so typography does not depend on locally
installed fonts.

## Colour

Generated, not picked. `scripts/build_palette.py` builds every family in OKLCH
on **one shared lightness spine**, so step 600 is the same perceptual lightness
in teal as it is in red, step 200 is the same hairline weight in every hue. That
shared spine — not a smaller number of hues — is what makes six families read as
one system. Run the script after any hue change and keep its contrast report at
zero failures.

| Family | Meaning |
|---|---|
| paper | warm neutral ground |
| teal | the system's own voice |
| violet | private, earphone-only moments |
| amber | unverified, simulated, AI-added |
| red | stop and refusal |
| green | confirmed |

`styles.css` splits these into two layers: **primitives** (`--teal-600`) and
**semantic roles** (`--teal`, `--violet-soft`). Components only ever reference
the semantic layer, so re-theming means re-pointing aliases and never touching a
component rule.

Status is never carried by colour alone — uncertain fragments and AI-added spans
also take a dashed outline, and the voice badge carries a glyph.

## Type

Three roles, not one stack:

- `--font-display` — headings, buttons, and anything that is *speech*: candidate
  sentences, the final expression, the capture clock. The web demo uses the
  Apple system stack first so the prototype matches the intended SwiftUI
  implementation and respects Dynamic Type-style scaling.
- `--font-text` — body copy, labels, the trace.
- `--font-mono` — hashes and identifiers, which are data to compare rather than
  prose.

CJK faces are listed on every role because the interface is bilingual.

Scale: 11 · 12 · 13 · 15 · 16 · 18 · 20 · 24, then two fluid display sizes. All
in `rem` and the root font-size is never set in px, so the OS text-size setting
scales the whole interface. Verified legible and fully operable at 150%.

The lockup SVG sources retain their designed live-text stacks for editing, while
the shipped PNG lockups are the portable assets used by the app.
