"""Render docs/og-preview.png (1200x630 social card) and docs/favicon.png (32x32) with pacta_raster.

  python3 tools/make_og.py --font-dir /path/to/ibm-plex-ttf [--out-dir docs]

Needs IBMPlexSans-SemiBold.ttf, IBMPlexSans-Regular.ttf, IBMPlexMono-Medium.ttf and IBMPlexMono-Regular.ttf
(IBM Plex, SIL Open Font License; https://github.com/IBM/plex). Fonts are read only at build time.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pacta_raster import TTF, Canvas, measure, wrap, write_png  # noqa: E402

BG, SURFACE, SURFACE2, BORDER = "#0b1017", "#111927", "#172234", "#23324a"
TEXT, MUTED, ACCENT = "#e6edf3", "#94a3b8", "#38bdf8"
HEADLINE = "Know when the people who control your DeFi collateral can change the rules — before they do."


def og(fonts, path):
    sans_sb, sans, mono_md, mono = fonts
    W, H = 1200, 630
    cv = Canvas(W, H, BG)
    for x in range(0, W, 40):                                   # faint grid
        cv.rect(x, 0, x + 1, H, MUTED, 0.035)
    for y in range(0, H, 40):
        cv.rect(0, y, W, y + 1, MUTED, 0.035)
    for r in range(440, 40, -8):                                # soft accent glow, top right (fine steps, no banding)
        cv.circle(1080, 40, r, ACCENT, 0.0045)
    cv.rect(0, 0, W, 6, ACCENT, 0.9)                            # top rule
    # brand row: mark + wordmark
    cv.rounded(64, 52, 104, 92, 9, SURFACE2, border=ACCENT, bw=2.5)
    cv.text(sans_sb, "P", 74, 84, 30, ACCENT)
    cv.circle(96, 84, 3.2, TEXT)
    cv.text(mono_md, "PACTA · FRACTAL NEURONS", 122, 81, 22, ACCENT, tracking=2.4)
    cv.text(mono, "PACTA SUNT SERVANDA", W - 64 - measure(mono, "PACTA SUNT SERVANDA", 16, 2.0), 80, 16, MUTED, tracking=2.0)
    # headline
    y = 178
    for ln in wrap(sans_sb, HEADLINE, 54, W - 128):
        cv.text(sans_sb, ln, 64, y, 54, TEXT)
        y += 66
    # control-plane diagram: Safe 4-of-7 -> 48h Timelock -> Proxy
    boxes = [("Safe", "4-of-7 multisig"), ("Timelock", "48h minDelay"), ("Proxy", "EIP-1967 admin")]
    bw_, bh_, gap, top = 300, 104, 86, 418
    x = 64
    for i, (title, sub) in enumerate(boxes):
        hot = i == 1
        cv.rounded(x, top, x + bw_, top + bh_, 14, SURFACE, border=ACCENT if hot else BORDER, bw=2.0 if hot else 1.5)
        cv.text(sans_sb, title, x + 24, top + 46, 30, TEXT)
        cv.text(mono, sub, x + 24, top + 80, 19, ACCENT if hot else MUTED)
        if i < 2:
            cv.arrow(x + bw_ + 14, top + bh_ / 2, x + bw_ + gap - 14, ACCENT, w=3.0, head=13)
        x += bw_ + gap
    # footer
    cv.rect(64, 560, W - 64, 561, BORDER)
    cv.text(mono, "Block-pinned control-plane snapshots · reproducible on any archive node", 64, 598, 17, MUTED)
    url = "pacta.wtf"
    cv.text(mono_md, url, W - 64 - measure(mono_md, url, 20), 599, 20, ACCENT)
    return write_png(path, cv)


def favicon(fonts, path):
    sans_sb = fonts[0]
    cv = Canvas(32, 32, BG, alpha=True)
    cv.rounded(0, 0, 32, 32, 7, BG)
    cv.rounded(0.5, 0.5, 31.5, 31.5, 7, BG, border=ACCENT, bw=1.6)
    cv.text(sans_sb, "P", 8.2, 24.5, 22, ACCENT)
    cv.circle(24, 24, 2.2, TEXT)
    return write_png(path, cv)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font-dir", required=True)
    ap.add_argument("--out-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs"))
    a = ap.parse_args()
    f = lambda n: TTF(os.path.join(a.font_dir, n))
    fonts = (f("IBMPlexSans-SemiBold.ttf"), f("IBMPlexSans-Regular.ttf"), f("IBMPlexMono-Medium.ttf"), f("IBMPlexMono-Regular.ttf"))
    print("og-preview.png bytes", og(fonts, os.path.join(a.out_dir, "og-preview.png")))
    print("favicon.png bytes", favicon(fonts, os.path.join(a.out_dir, "favicon.png")))


if __name__ == "__main__":
    main()
