#!/usr/bin/env python3
"""render_x_cards_raster.py - the 1200x675 X-feed receipt cards (docs/cards/<cardFilename>) in pure Python with pacta_raster (no Pillow).

    python3 tools/render_x_cards_raster.py --font-dir <ibm-plex-ttf> [--feed docs/api/v1/x-feed.json] [--out docs/cards] [--only slug,...]

Same layout as pacta-core packages/x-feed/build_x_cards.py (#f7f7f5 page, #ffffff rounded card, #e1e1dc borders, "PACTA control-plane
receipt" + status badge, protocol name, @handle + chain / block / sprint, the two-row Published docs vs On-chain comparison, the 5-factor
rosette with S / M / W / — cues and strong / medium / weak / not determined, footer), set in IBM Plex Sans. write_png stores no text
chunks and no timestamp, so the bytes are deterministic for a given feed item and font files.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pacta_raster import TTF, Canvas, measure, write_png  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
W, H = 1200, 675
PAGE, CARD, BORDER, INK, MUTED, FAINT = "#f7f7f5", "#ffffff", "#e1e1dc", "#1c1c1a", "#5f5f5a", "#5f5f5a"   # NS-01: informative text >= 6.4:1 on white
BADGE = {
    "adverse_delta": ("Delta", "#fdf2dc", "#8a4b08"),
    "protective_delta": ("Protective", "#dff3f0", "#115e59"),
    "unresolved_scope": ("Unresolved", "#eceef2", "#3b4252"),
    "recent_change": ("Changed recently", "#e0f2fe", "#075985"),
    "docs_updated": ("Docs updated", "#eceef2", "#3b4252"),
    "aligned_baseline": ("Aligned", "#efefec", "#3a3a36"),
    "rpc_observed": ("RPC-observed", "#eceef2", "#3b4252"),
    "radar_timelock": ("Timelock watch", "#eceef2", "#3b4252"),
}
CUE_INK = {"S": "#1c1c1a", "M": "#5f5f5a", "W": "#8a4b08", "—": "#5f5f5a"}
STATE_WORD = {"g": "strong", "b": "medium", "a": "weak", "n": "not determined", "u": "not compared"}
SHORT = {"upgrade": "Upgrades", "timelock": "Timelock", "quorum": "Signers", "emergency": "Emergency", "parity": "Docs vs chain"}
ASC = 0.78   # Pillow draws text from its top; pacta_raster from the baseline: baseline = top + ASC * size


class Fonts:
    def __init__(self, d):
        self.reg = TTF(os.path.join(d, "IBMPlexSans-Regular.ttf"))
        self.semi = TTF(os.path.join(d, "IBMPlexSans-SemiBold.ttf"))

    def __call__(self, weight):
        return self.semi if weight >= 600 else self.reg


def cap(t):
    return t[:1].upper() + t[1:]


def wrap(f, text, size, width, max_lines):
    words, lines, cur = text.split(), [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if measure(f, cand, size) <= width:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and measure(f, last + "…", size) > width:
            last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
        lines[-1] = last + "…"
    return lines


def text(cv, f, s, x, top, size, color):
    cv.text(f, s, x, top + ASC * size, size, color)


def render(item, F):
    cv = Canvas(W, H, bg=PAGE)
    x0, y0, x1, y1 = 40, 36, W - 40, H - 36
    cv.rounded(x0, y0, x1, y1, 18, CARD, border=BORDER, bw=2.0)
    px = x0 + 48
    text(cv, F(700), "PACTA", px, y0 + 34, 20, INK)
    text(cv, F(400), "control-plane receipt", px + 86, y0 + 34, 20, FAINT)
    label, bg, fg = BADGE[item["kind"]]
    bw = measure(F(600), label, 20) + 36
    cv.rounded(x1 - 48 - bw, y0 + 26, x1 - 48, y0 + 66, 20, bg)
    text(cv, F(600), label, x1 - 48 - bw + 18, y0 + 34, 20, fg)
    size, name = 44, item["protocolName"]
    while measure(F(650), name, size) > x1 - px - 60 and size > 30:
        size -= 2
    text(cv, F(650), name, px, y0 + 92, size, INK)
    sub = item.get("xHandle") or ""
    chain = {"ethereum": "Ethereum", "base": "Base"}[item["chain"]]
    meta = f"{chain} · block #{item['pinnedBlock']:,}" + (f" · Sprint {item['sprint']}" if item.get("sprint") else "")
    text(cv, F(450), (sub + "   " if sub else "") + meta, px, y0 + 150, 24, MUTED)
    top, bx1 = y0 + 204, x1 - 48
    cv.rect(px, top - 1, bx1, top + 1, BORDER)
    on = f"On-chain at {chain} block #{item['pinnedBlock']:,}"
    k = item["kind"]
    if k == "radar_timelock":
        rows = [("Queued change", item["docsSay"]), (on, cap(item["chainSays"]))]
    elif k == "aligned_baseline":
        rows = [("Published docs", cap(item["docsSay"])), (on, "Matches the docs")]
    elif k == "rpc_observed":
        rows = [("Published docs", "Not compared yet"), (on, cap(item["chainSays"]))]
    elif k in ("unresolved_scope", "recent_change", "docs_updated"):
        rows = [("Published docs", cap(item["docsSay"])), (f"Observed at {chain} block #{item['pinnedBlock']:,}", cap(item["chainSays"]))]
    else:
        rows = [("Published docs", cap(item["docsSay"])), (on, cap(item["chainSays"]))]
    y = top + 18
    for i, (lab, txt) in enumerate(rows):
        text(cv, F(600), lab.upper(), px, y, 19, FAINT)
        lines = wrap(F(450), txt, 28, bx1 - px, 2)
        for j, ln in enumerate(lines):
            text(cv, F(450), ln, px, y + 30 + j * 36, 28, INK)
        y += 30 + 36 * max(1, len(lines)) + 18
        if i == 0:
            cv.rect(px, y - 9, bx1, y - 8, BORDER)
    ry = y1 - 150
    cv.rect(px, ry - 15, bx1, ry - 13, BORDER)
    cw = (bx1 - px) / 5
    for i, f in enumerate(item["rosette"]):
        cx = px + i * cw
        cue = f["cue"]
        cv.rounded(cx, ry, cx + 46, ry + 46, 10, CARD, border=BORDER, bw=2.0)
        text(cv, F(700), cue, cx + 23 - measure(F(700), cue, 24) / 2, ry + 9, 24, CUE_INK[cue])
        text(cv, F(600), SHORT.get(f["key"], f["label"]), cx + 58, ry + 2, 19, INK)
        text(cv, F(400), STATE_WORD[f["state"]], cx + 58, ry + 26, 17, FAINT)
    attested = bool(item.get("easUid"))
    foot = "Base Mainnet EAS Verified · pacta.wtf" if attested else "Pinned on-chain observation · pacta.wtf"
    text(cv, F(600 if attested else 450), foot, px, y1 - 62, 20, INK if attested else MUTED)
    leg = "S strong · M medium · W weak · — not determined"
    text(cv, F(400), leg, bx1 - measure(F(400), leg, 17), y1 - 60, 17, FAINT)
    return cv


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--font-dir", required=True)
    ap.add_argument("--feed", default=os.path.join(ROOT, "docs", "api", "v1", "x-feed.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "cards"))
    ap.add_argument("--only", default=None, help="comma list of slugs / feedIds")
    a = ap.parse_args(argv)
    F = Fonts(a.font_dir)
    only = set(a.only.split(",")) if a.only else None
    items = [i for i in json.load(open(a.feed, encoding="utf-8"))["items"] if not only or i["slug"] in only or i["feedId"] in only]
    assert items, "no feed item matched"
    for it in items:
        assert all(r["cue"] in CUE_INK and r["state"] in STATE_WORD for r in it["rosette"]), it["feedId"]
        write_png(os.path.join(a.out, it["cardFilename"]), render(it, F))
    print(f"rendered {len(items)} cards -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
