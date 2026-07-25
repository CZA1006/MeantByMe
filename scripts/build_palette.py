"""Regenerate the interface palette and check it against WCAG AA.

The palette in ``services/web_demo/static/styles.css`` is not hand-picked. Every
family is generated here in OKLCH on one shared lightness spine, so step 600 is
the same perceptual lightness in teal as it is in red, step 200 is the same
hairline weight in every hue, and so on. That shared spine is what makes six
colour families read as a single system.

Run it after changing any hue or chroma, paste the printed block into the
``:root`` primitives in ``styles.css``, and keep the contrast report at zero
failures.

    python scripts/build_palette.py
"""

from __future__ import annotations

import math

# ── Roles on the shared lightness spine ─────────────────────────────────────
#   50   tint background        400  icon / mid
#   100  soft background        600  solid fill (white text passes AA)
#   200  hairline               700  text on the family's own 50 / 100
STEPS: dict[str, float] = {
    "50": 0.975,
    "100": 0.945,
    "200": 0.885,
    "300": 0.800,
    "400": 0.680,
    "600": 0.545,
    "700": 0.455,
}

# family -> (hue in degrees, chroma per step)
FAMILIES: dict[str, tuple[int, dict[str, float]]] = {
    "paper": (68, {"50": 0.006, "100": 0.010, "200": 0.014, "300": 0.014,
                   "400": 0.014, "600": 0.014, "700": 0.014}),
    "teal": (192, {"50": 0.016, "100": 0.030, "200": 0.045, "300": 0.060,
                   "400": 0.075, "600": 0.085, "700": 0.075}),
    "violet": (285, {"50": 0.016, "100": 0.030, "200": 0.050, "300": 0.080,
                     "400": 0.110, "600": 0.150, "700": 0.140}),
    "amber": (85, {"50": 0.030, "100": 0.060, "200": 0.085, "300": 0.100,
                   "400": 0.110, "600": 0.110, "700": 0.095}),
    "red": (25, {"50": 0.016, "100": 0.030, "200": 0.050, "300": 0.080,
                 "400": 0.110, "600": 0.150, "700": 0.140}),
    "green": (150, {"50": 0.016, "100": 0.032, "200": 0.050, "300": 0.070,
                    "400": 0.090, "600": 0.110, "700": 0.100}),
}

INK = {"900": (0.245, 0.018, 195), "700": (0.400, 0.016, 195),
       "500": (0.510, 0.014, 195)}
SURFACE = (0.992, 0.004, 68)
CANVAS = (0.905, 0.010, 68)
FOCUS = (0.500, 0.190, 262)


def oklch_to_hex(lightness: float, chroma: float, hue_deg: float) -> str:
    """Convert an OKLCH triple to a clipped sRGB hex string."""
    hue = math.radians(hue_deg)
    a, b = chroma * math.cos(hue), chroma * math.sin(hue)
    l_ = lightness + 0.3963377774 * a + 0.2158037573 * b
    m_ = lightness - 0.1055613458 * a - 0.0638541728 * b
    s_ = lightness - 0.0894841775 * a - 1.2914855480 * b
    light_cubed, mid_cubed, short_cubed = l_**3, m_**3, s_**3
    linear = (
        +4.0767416621 * light_cubed
        - 3.3077115913 * mid_cubed
        + 0.2309699292 * short_cubed,
        -1.2684380046 * light_cubed
        + 2.6097574011 * mid_cubed
        - 0.3413193965 * short_cubed,
        -0.0041960863 * light_cubed
        - 0.7034186147 * mid_cubed
        + 1.7076147010 * short_cubed,
    )
    channels = []
    for value in linear:
        encoded = (
            1.055 * value ** (1 / 2.4) - 0.055 if value > 0.0031308
            else 12.92 * value
        )
        channels.append(round(max(0.0, min(1.0, encoded)) * 255))
    return "#%02x%02x%02x" % tuple(channels)


def _channel_luminance(value: int) -> float:
    scaled = value / 255
    if scaled <= 0.03928:
        return scaled / 12.92
    return ((scaled + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_colour: str) -> float:
    raw = hex_colour.lstrip("#")
    red, green, blue = (int(raw[i:i + 2], 16) for i in (0, 2, 4))
    return (
        0.2126 * _channel_luminance(red)
        + 0.7152 * _channel_luminance(green)
        + 0.0722 * _channel_luminance(blue)
    )


def contrast(foreground: str, background: str) -> float:
    first, second = relative_luminance(foreground), relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def build() -> dict[str, dict[str, str]]:
    ramps = {}
    for family, (hue, chroma) in FAMILIES.items():
        ramps[family] = {
            step: oklch_to_hex(lightness, chroma[step], hue)
            for step, lightness in STEPS.items()
        }
    return ramps


def main() -> int:
    ramps = build()
    surface = oklch_to_hex(*SURFACE)
    canvas = oklch_to_hex(*CANVAS)
    ink = {name: oklch_to_hex(*value) for name, value in INK.items()}
    focus = oklch_to_hex(*FOCUS)

    print("── primitives ──")
    for family, ramp in ramps.items():
        for step in STEPS:
            print(f"  --{family}-{step}: {ramp[step]};")
    for name, value in ink.items():
        print(f"  --ink-{name}: {value};")
    print(f"  --white: {surface};")
    print(f"  --blue-600: {focus};")
    print(f"  --canvas: {canvas};")

    # Only the pairs the interface actually renders are worth asserting.
    checks = [
        ("ink-900 on surface", ink["900"], surface, 4.5),
        ("ink-700 on surface", ink["700"], surface, 4.5),
        ("ink-500 on surface", ink["500"], surface, 4.5),
        ("ink-500 on paper-50", ink["500"], ramps["paper"]["50"], 4.5),
        ("ink-500 on paper-100", ink["500"], ramps["paper"]["100"], 4.5),
        ("white on teal-600", surface, ramps["teal"]["600"], 4.5),
        ("teal-700 on teal-50", ramps["teal"]["700"], ramps["teal"]["50"], 4.5),
        ("teal-700 on surface", ramps["teal"]["700"], surface, 4.5),
        ("violet-600 on violet-50", ramps["violet"]["600"], ramps["violet"]["50"], 4.5),
        ("violet-600 on surface", ramps["violet"]["600"], surface, 4.5),
        ("amber-700 on amber-50", ramps["amber"]["700"], ramps["amber"]["50"], 4.5),
        ("red-700 on red-50", ramps["red"]["700"], ramps["red"]["50"], 4.5),
        ("red-700 on surface", ramps["red"]["700"], surface, 4.5),
        ("green-700 on green-50", ramps["green"]["700"], ramps["green"]["50"], 4.5),
        ("focus on surface", focus, surface, 3.0),
        ("paper-200 hairline on surface", ramps["paper"]["200"], surface, 1.2),
    ]

    print("\n── contrast ──")
    failures = 0
    for label, foreground, background, required in checks:
        measured = contrast(foreground, background)
        passed = measured >= required
        failures += not passed
        print(f"  {measured:6.2f} {'ok  ' if passed else 'FAIL'} {label} "
              f"(needs {required})")

    print(f"\n{failures} failing")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
