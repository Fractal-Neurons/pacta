#!/usr/bin/env python3
"""Render docs/miniapp-preview.png (1200x800, 3:2 Farcaster / Base Mini-App embed card) deterministically with pacta_raster.

  python3 tools/make_miniapp_card.py --font-dir /home/pacta-gemini/workspace/shared-specs/ibm-plex-ttf
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pacta_raster import TTF, Canvas, draw_pacta_logo, measure, write_png  # noqa: E402

W, H = 1200, 800
D_BG = "#0a0b0d"
D_PANEL = "#101216"
D_CARD = "#141820"
D_INK = "#e8eaed"
D_MUTED = "#9aa0aa"
D_LINE = "#23262c"
D_ACCENT = "#a3b8ec"
D_GREEN_BG, D_GREEN_FG = "#0d2818", "#6ee7b7"
D_AMBER_BG, D_AMBER_FG = "#2c1f0b", "#fcd34d"
D_BLUE_BG, D_BLUE_FG = "#132038", "#93c5fd"


def pill(cv, font, x, y, text, bg, fg, border, size=17, pad_x=16, h=40):
    tw = measure(font, text, size)
    w = tw + pad_x * 2
    cv.rounded(x, y, x + w, y + h, 8, bg, border=border, bw=1.0)
    cv.text(font, text, x + pad_x, y + 27, size, fg)
    return x + w


def render_miniapp_card(font_dir, out_path):
    sans_sb = TTF(os.path.join(font_dir, "IBMPlexSans-SemiBold.ttf"))
    sans = TTF(os.path.join(font_dir, "IBMPlexSans-Regular.ttf"))
    mono_md = TTF(os.path.join(font_dir, "IBMPlexMono-Medium.ttf"))
    mono = TTF(os.path.join(font_dir, "IBMPlexMono-Regular.ttf"))

    cv = Canvas(W, H, D_BG)
    cv.rounded(48, 44, W - 48, H - 44, 16, D_PANEL, border=D_LINE, bw=1.5)
    X, R = 88, W - 88

    # Brand header
    draw_pacta_logo(cv, X, 76, 38, ss=8)
    cv.text(sans_sb, "PACTA", X + 52, 104, 22, D_INK, tracking=2.0)
    bx = X + 52 + measure(sans_sb, "PACTA", 22, 2.0) + 16
    cv.rect(bx, 84, bx + 1, 108, D_LINE)
    cv.text(mono_md, "BASE & FARCASTER MINI-APP", bx + 16, 103, 17, D_ACCENT, tracking=1.0)
    tag_txt = "BASE · ETHEREUM"
    pill(cv, mono_md, R - measure(mono_md, tag_txt, 16) - 34, 76, tag_txt, D_BLUE_BG, D_BLUE_FG, "#26406e", size=16, pad_x=17, h=38)
    cv.rect(X, 136, R, 137, D_LINE)

    # Eyebrow + 2-line headline
    cv.text(mono_md, "PRE-DEPOSIT CONTROL-PLANE CHECK", X, 184, 16, D_ACCENT, tracking=1.6)
    cv.text(sans_sb, "Docs promise a 48h timelock.", X, 246, 52, D_INK)
    cv.text(sans_sb, "What does the chain say?", X, 310, 52, D_ACCENT)
    cv.text(sans, "Paste any 0x contract on Base or Ethereum for a block-pinned authority verdict.", X, 362, 23, D_MUTED)

    # Clinical terminal card
    cv.rounded(X, 396, R, 636, 12, D_CARD, border=D_LINE, bw=1.0)
    px = X + 28
    px = pill(cv, mono_md, px, 422, "ALIGNED · DOCS = CHAIN", D_GREEN_BG, D_GREEN_FG, "#1b4d30")
    px = pill(cv, mono_md, px + 14, 422, "DOCS DIFFER · 0s MULTISIG", D_AMBER_BG, D_AMBER_FG, "#5c3f14")
    pill(cv, mono_md, px + 14, 422, "BASE EAS ATTESTED", D_BLUE_BG, D_BLUE_FG, "#26406e")

    cv.rect(X + 28, 482, R - 28, 483, D_LINE)
    cv.text(mono_md, "PROXY & ADMIN", X + 28, 520, 18, D_MUTED)
    cv.text(mono, "EIP-1967 implementation + ProxyAdmin / UUPS authority", X + 250, 520, 18, D_INK)
    cv.text(mono_md, "CONTROLLER", X + 28, 560, 18, D_MUTED)
    cv.text(mono, "Safe M-of-N signers · TimelockController minDelay()", X + 250, 560, 18, D_INK)
    cv.text(mono_md, "1-TAP UPGRADE", X + 28, 600, 18, D_MUTED)
    cv.text(mono_md, "$19 Full Deep-Scan  ·  $99 24h Mainnet EAS Seal (Base USDC)", X + 250, 600, 18, D_ACCENT)

    # Bottom CTA pill + reassurance
    cta = "pacta.wtf/miniapp"
    pw = measure(mono_md, cta, 19) + 74
    cv.rounded(X, 668, X + pw, 718, 8, D_BG, border=D_LINE, bw=1.0)
    cv.text(mono_md, cta, X + 22, 700, 19, D_INK)
    cv.arrow(X + pw - 42, 693, X + pw - 18, D_ACCENT, w=2.5, head=9.0)
    cv.text(sans, "Instant Free Check  ·  Zero Token Approvals  ·  Base USDC", X + pw + 26, 700, 21, D_MUTED)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    write_png(out_path, cv)
    sz = os.path.getsize(out_path)
    assert sz <= 500 * 1024, f"miniapp-preview.png exceeds 500 KB ({sz} B)"
    print(f"wrote {out_path} ({W}x{H}, {sz:,} bytes)")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--font-dir", default="/home/pacta-gemini/workspace/shared-specs/ibm-plex-ttf")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "miniapp-preview.png"))
    args = ap.parse_args()
    render_miniapp_card(args.font_dir, args.out)


if __name__ == "__main__":
    main()
