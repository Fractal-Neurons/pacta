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

import json  # noqa: E402

# v3 Paper palette (matches docs/styles.css)
BG, INK, INK2, MUTED, LINE, LINE2, ACCENT = "#f7f7f5", "#14161a", "#353a42", "#5f6570", "#e1e1dc", "#cdcdc6", "#1d4ed8"
HEADLINE = "Know when the people who control your DeFi collateral can change the rules — before they do."
DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")


def metrics():
    idx = json.load(open(os.path.join(DOCS, "api", "v1", "index.json")))
    m = idx["summary_metrics"]
    eas = len(idx["onchain_anchoring"]["sprint_eas_attestations"])
    return [(str(m["sprints_completed"]), "Sprints completed"), (str(m["records_indexed"]), "Verified surfaces"),
            (str(eas), "Base EAS attestations"), ("24h", "Issuer clearance SLA")]


def og(fonts, path):
    sans_sb, sans, mono_md, mono = fonts
    W, H, X = 1200, 630, 72
    cv = Canvas(W, H, BG)
    cv.rect(0, 0, W, 5, ACCENT)                                 # restrained cobalt top rule
    # brand row: mark + wordmark, domain on the right
    cv.rounded(X, 54, X + 34, 88, 3, INK)
    cv.text(sans_sb, "P", X + 9, 80, 24, BG)
    cv.circle(X + 26, 80, 2.4, "#a3b8ec")
    cv.text(sans_sb, "PACTA", X + 48, 79, 21, INK, tracking=2.2)
    bx = X + 48 + measure(sans_sb, "PACTA", 21, 2.2) + 16
    cv.rect(bx, 60, bx + 1, 84, LINE2)
    cv.text(sans, "by Fractal Neurons", bx + 16, 79, 19, MUTED)
    dom = "pacta.wtf"
    cv.text(mono_md, dom, W - X - measure(mono_md, dom, 19), 79, 19, INK2)
    cv.rect(X, 116, W - X, 117, LINE2)
    # headline
    y = 196
    for ln in wrap(sans_sb, HEADLINE, 52, W - 2 * X - 40):
        cv.text(sans_sb, ln, X, y, 52, INK)
        y += 64
    # metrics ledger: hairline-separated columns
    top = 444
    cv.rect(X, top, W - X, top + 1, LINE2)
    cols = metrics()
    cw = (W - 2 * X) / len(cols)
    for i, (num, label) in enumerate(cols):
        cx = X + i * cw + (0 if i == 0 else 26)
        if i:
            cv.rect(X + i * cw, top + 1, X + i * cw + 1, top + 104, LINE)
        cv.text(sans_sb, num, cx, top + 58, 40, INK)
        cv.text(sans, label, cx, top + 88, 18, MUTED)
    cv.rect(X, top + 104, W - X, top + 105, LINE)
    cv.text(mono, "Block-pinned control-plane snapshots · reproducible on any archive node", X, 596, 16, MUTED)
    return write_png(path, cv)


def favicon(fonts, path):
    sans_sb = fonts[0]
    cv = Canvas(32, 32, BG, alpha=True)
    cv.rounded(0, 0, 32, 32, 3, INK)
    cv.text(sans_sb, "P", 8.4, 24.5, 22, BG)
    cv.circle(24.2, 24.2, 2.2, "#a3b8ec")
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
