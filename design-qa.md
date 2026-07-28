# MeantByMe QR Hub Design QA

- English implementation (default): [`docs/index.html`](docs/index.html)
- Chinese implementation: [`docs/zh.html`](docs/zh.html)
- Brand sources:
  [`docs/assets/logo-lockup-en-dark.svg`](docs/assets/logo-lockup-en-dark.svg)
  and [`docs/assets/logo-lockup-zh-dark.svg`](docs/assets/logo-lockup-zh-dark.svg)
- Visual-reference and viewport screenshots were generated during the design QA
  session and are intentionally not treated as portable source files.
- Desktop viewport: 1440 × 1024 CSS px, device scale factor 1
- Mobile viewport: 390 × 844 CSS px, device scale factor 1
- Source pixels: 1536 × 1024
- Desktop implementation pixels: 1440 × 1024
- Mobile implementation pixels: 390 × 844
- State: initial page load with the native video player visible

## Full-view comparison evidence

The source and desktop implementation were placed in one 2880 × 1024 comparison image. Both use the selected direction's dark immersive hero, left-aligned bilingual value proposition, coral primary action, large video stage, warm-paper consent flow, and restrained resource hierarchy. The implementation intentionally substitutes the actual demo frame and the official `frontend` branch logo for the concept's illustrative video surface and generic wordmark.

## Focused region evidence

The 390 × 844 mobile viewport was captured separately because mobile QR traffic is a primary use case. It shows the complete logo, bilingual hero, consent copy, primary CTA, and usable native video controls without horizontal overflow. `documentElement.scrollWidth` equals the 390 px viewport width.

## Required fidelity surfaces

- Fonts and typography: system UI and CJK fallbacks preserve the mock's bold bilingual hierarchy, readable body scale, and compact metadata. Display wrapping remains controlled at desktop and mobile widths.
- Spacing and layout rhythm: the desktop two-column hero, section transitions, three-step flow, and resource rows follow the source proportions. Mobile collapses to a single column with 36 px total side margins and large tap targets.
- Colors and visual tokens: dark forest hero, warm paper, coral action color, and the logo's teal/violet authorization colors match the selected direction and existing brand assets.
- Image quality and asset fidelity: the official vector logo from `origin/frontend` is used without reconstruction. Both players use the versioned 592 × 1280, 30 fps MP4 and native browser controls.
- Copy and content: all five original destinations remain. Consent copy follows repository invariants and does not claim diagnosis, clinical accuracy, autonomous authorization, or unconfirmed personal-voice use.

## Interaction and runtime checks

- The English root is the default page and the Chinese edition is available at
  `/zh.html`.
- The EN / 中文 controls switch between the two standalone localized pages and
  expose the current page with `aria-current="page"`.
- The primary demo CTA resolves uniquely and scrolls to `#demo` in both
  languages.
- The native MP4 metadata loads and reports a 1:17 duration.
- The decoded video reports 592 × 1280 pixels rather than the superseded 88 × 192 release asset.
- All five resource links are present with their intended href values.
- Both languages render at 1440 × 1024 and 390 × 844 with no horizontal
  overflow; the language control remains visible at mobile width.
- Browser console warnings/errors checked: none.

## Comparison history

### Iteration 1

- Finding: P2 — the first mobile capture made the display title appear oversized and the full-page capture showed an unreliable blank region after the native video.
- Fix: reduced the mobile display scale to `clamp(43px, 12.2vw, 52px)` and switched verification to the actual 390 × 844 viewport state.
- Post-fix evidence: the mobile viewport screenshot shows the full `MeantByMe 意由我` title, CTA, and video stage without overflow; DOM bounds confirm the following sections remain contiguous.

### Iteration 2

- Finding: P1 — the release-hosted video decoded at only 88 × 192 pixels,
  15 fps and approximately 55 Kbps, then scaled to a 560px-tall desktop player.
- Fix: uploaded the original 592 × 1280, 30 fps H.264/AAC source as
  `meantbyme-demo-v2.mp4` and updated both `docs/index.html` and
  `docs/demo.html` to use the versioned URL.
- Post-fix evidence: the release digest matches the provided source and the
  browser decodes the new asset at 592 × 1280.

### Iteration 3

- Finding: the hub had only a Chinese page and therefore could not make English
  the default without mixing both languages into one document.
- Fix: localized the root page in English, added a dedicated `/zh.html` page,
  used the official English and Chinese lockups, and added a persistent language
  switch.
- Post-fix evidence: browser checks confirm the English root, Chinese route,
  active-language state, localized slogans, functional switching, and
  overflow-free desktop and mobile layouts.

## Findings

No actionable P0, P1, or P2 differences remain. The official logo and actual portrait demo footage are intentional product-truth deviations from the generated visual concept.

## Follow-up polish

- P3: add a purpose-made poster frame to the release video later if the team wants a more art-directed paused state.

## Final result

final result: passed
