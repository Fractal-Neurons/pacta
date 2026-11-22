"""Render the 1200 x 628 (1.91:1) social cards, docs/favicon.png (32x32) and docs/logo-512.png (512x512) with pacta_raster; the mark
is the official Pacta logo (docs/logo.svg) drawn by pacta_raster.draw_pacta_logo. Deterministic: no clock, no randomness.

  python3 tools/make_og.py --font-dir /path/to/ibm-plex-ttf [--out-dir docs]

Social cards (X Website cards crop anything that is not 1.91:1 and lay a headline pill over the bottom-left ~96 px):
  docs/og-preview.png                              sitewide og:image / twitter:image
  docs/cards/x-card-scorecards-1200x628.png        /scorecards/
  docs/cards/x-card-scan19-1200x628.png            /scan/ ($9 USDC wallet & Safe report) and /request/
  docs/cards/x-card-seal99-1200x628.png            /seal/ (mainnet re-verification by arrangement)
Every card keeps >= 96 px clear on the left and right and >= 120 px clear at the bottom: nothing (text, badge or border) is drawn
there, and render() refuses to write a card that touches a safe zone.

Needs IBMPlexSans-SemiBold.ttf, IBMPlexSans-Regular.ttf, IBMPlexMono-Medium.ttf and IBMPlexMono-Regular.ttf
(IBM Plex, SIL Open Font License; https://github.com/IBM/plex). Fonts are read only at build time.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pacta_raster import TTF, Canvas, draw_pacta_logo, hex_rgb, measure, wrap, write_png  # noqa: E402

# v3 Paper palette (favicon / logo backgrounds; matches docs/styles.css :root)
BG = "#f7f7f5"
# dark institutional palette for the social cards (docs/styles.css .dark)
D_BG, D_PANEL, D_INK, D_MUTED, D_LINE, D_ACCENT = "#0a0b0d", "#101216", "#e8eaed", "#9aa0aa", "#23262c", "#a3b8ec"
W, H = 1200, 628                                   # X Website card, 1.91:1
SAFE_X, SAFE_BOTTOM = 96, 120                      # clear margins (left / right, bottom)
PANEL = (SAFE_X, 36, W - SAFE_X, H - SAFE_BOTTOM - 8)
DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")


def counts():
    idx = json.load(open(os.path.join(DOCS, "api", "v1", "index.json")))
    n = len(json.load(open(os.path.join(DOCS, "api", "v1", "protocols.json")))["protocols"])
    return n, len(idx["onchain_anchoring"]["sprint_eas_attestations"])


def base(fonts):
    """The dark panel and its brand row (mark, wordmark, domain, hairline); returns the canvas and the content box x range."""
    sans_sb, sans, mono_md, _ = fonts
    cv = Canvas(W, H, D_BG)
    x0, y0, x1, y1 = PANEL
    cv.rounded(x0, y0, x1, y1, 14, D_PANEL, border=D_LINE, bw=1.0)
    X, R = x0 + 32, x1 - 32
    draw_pacta_logo(cv, X, y0 + 28, 34, ss=8)
    cv.text(sans_sb, "PACTA", X + 48, y0 + 54, 20, D_INK, tracking=2.0)
    bx = X + 48 + measure(sans_sb, "PACTA", 20, 2.0) + 14
    cv.rect(bx, y0 + 36, bx + 1, y0 + 58, D_LINE)
    cv.text(sans, "by Fractal Neurons", bx + 14, y0 + 54, 18, D_MUTED)
    cv.text(mono_md, "pacta.wtf", R - measure(mono_md, "pacta.wtf", 18), y0 + 54, 18, D_MUTED)
    cv.rect(X, y0 + 84, R, y0 + 85, D_LINE)
    return cv, X, R


def offer(fonts, eyebrow, headline, sub, cta):
    """Eyebrow, a headline of at most two explicit lines, a muted sub-line and a CTA pill (the clean, query-free URL the card links to)."""
    sans_sb, sans, mono_md, _ = fonts
    cv, X, R = base(fonts)
    cv.text(mono_md, eyebrow, X, 168, 16, D_ACCENT, tracking=1.6)
    y = 226
    lines = list(headline)                          # explicit lines: a headline never breaks mid-phrase
    assert len(lines) <= 2 and all(measure(sans_sb, ln, 50) <= R - X for ln in lines), lines
    for ln in lines:
        cv.text(sans_sb, ln, X, y, 50, D_INK)
        y += 60
    y += 4
    subs = wrap(sans, sub, 22, R - X)
    assert len(subs) <= 2, subs
    for ln in subs:
        cv.text(sans, ln, X, y, 22, D_MUTED)
        y += 32
    pw = measure(mono_md, cta, 18) + 72
    cv.rounded(X, 418, X + pw, 460, 8, D_BG, border=D_LINE, bw=1.0)
    cv.text(mono_md, cta, X + 20, 445, 18, D_INK)
    cv.arrow(X + pw - 40, 439, X + pw - 18, D_ACCENT, w=2.5, head=9.0)
    return cv


def og(fonts):
    """Sitewide card: the homepage line and the live counts (protocols indexed, Base Mainnet EAS sprints)."""
    sans_sb, sans, _, mono = fonts
    n, sprints = counts()
    cv, X, R = base(fonts)
    for i, ln in enumerate(("Protocol docs drift.", "On-chain state doesn’t.")):
        cv.text(sans_sb, ln, X, 200 + 64 * i, 56, D_INK)
    top = 306
    cv.rect(X, top, R, top + 1, D_LINE)
    cols = ((str(n), "Indexed protocols"), (str(sprints), "Base Mainnet EAS sprints"), ("Zero-trust", "Control-plane verification"))
    cw = (R - X) / len(cols)
    for i, (num, label) in enumerate(cols):
        cx = X + i * cw + (0 if i == 0 else 24)
        if i:
            cv.rect(X + i * cw, top + 1, X + i * cw + 1, top + 106, D_LINE)
        cv.text(sans_sb, num, cx, top + 60, 40, D_INK)
        cv.text(sans, label, cx, top + 90, 17, D_MUTED)
    cv.rect(X, top + 106, R, top + 107, D_LINE)
    cv.text(mono, "Block-pinned control-plane snapshots · reproducible on any archive node", X, 466, 15, D_MUTED)
    return cv


def cards(fonts):
    n, _ = counts()
    return {
        "og-preview.png": og(fonts),
        "cards/x-card-scorecards-1200x628.png": offer(
            fonts, "PROTOCOL SCORECARDS", ("Who can upgrade, pause or change", f"{n} DeFi protocols?"),
            "Docs vs. chain for every protocol: proxy admins, Safes, timelocks and roles, block-pinned and attested on Base.",
            "pacta.wtf/scorecards"),
        # file names kept so the published og:image URLs stay valid; the copy is the $9 report and re-verification by arrangement
        "cards/x-card-scan19-1200x628.png": offer(
            fonts, "WALLET & SAFE EXPOSURE REPORT", ("$9 USDC · full wallet & Safe report", "on Ethereum and Base"),
            "Paste any wallet, Safe or contract address: free instant preflight check first, or $9 USDC full multi-position report.",
            "pacta.wtf/scan"),
        "cards/x-card-seal99-1200x628.png": offer(
            fonts, "MAINNET CONTROL-PLANE RE-VERIFICATION", ("Independent mainnet re-check", "and Base EAS attestation"),
            "Fixed a flagged gap or need a custom protocol dossier? Scoped and scheduled by arrangement at pacta@dri.network.",
            "pacta.wtf/request"),
    }


def assert_safe(cv, name):
    """Nothing may touch the clear margins: every pixel left of 96 px, right of 1104 px or in the bottom 120 px is the background."""
    bg = bytes(hex_rgb(D_BG))
    for y in range(H):
        row = cv.px[y * W * 3:(y + 1) * W * 3]
        if y >= H - SAFE_BOTTOM:
            assert row == bg * W, f"{name}: bottom safe zone touched at y={y}"
        else:
            assert row[:SAFE_X * 3] == bg * SAFE_X and row[(W - SAFE_X) * 3:] == bg * SAFE_X, f"{name}: side safe zone touched at y={y}"


def favicon(fonts, path):
    cv = Canvas(32, 32, BG, alpha=True)                         # transparent background
    draw_pacta_logo(cv, 0, 0, 32, ss=8)
    return write_png(path, cv)


def logo_512(path):
    cv = Canvas(512, 512, BG, alpha=True)                       # transparent background (Organization.logo, directories, avatars)
    draw_pacta_logo(cv, 0, 0, 512, ss=8)
    return write_png(path, cv)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font-dir", required=True)
    ap.add_argument("--out-dir", default=DOCS)
    ap.add_argument("--social-only", action="store_true", help="render only the four 1200 x 628 cards")
    a = ap.parse_args()
    f = lambda n: TTF(os.path.join(a.font_dir, n))
    fonts = (f("IBMPlexSans-SemiBold.ttf"), f("IBMPlexSans-Regular.ttf"), f("IBMPlexMono-Medium.ttf"), f("IBMPlexMono-Regular.ttf"))
    for rel, cv in cards(fonts).items():
        assert (cv.w, cv.h) == (W, H)
        assert_safe(cv, rel)
        print(rel, "bytes", write_png(os.path.join(a.out_dir, rel), cv))
    if not a.social_only:
        print("favicon.png bytes", favicon(fonts, os.path.join(a.out_dir, "favicon.png")))
        print("logo-512.png bytes", logo_512(os.path.join(a.out_dir, "logo-512.png")))


if __name__ == "__main__":
    main()
