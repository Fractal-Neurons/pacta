"""pacta_raster - dependency-free raster toolkit used to build the site's PNG assets (OG card, favicon).

Pure Python standard library: a TrueType (glyf) font reader (cmap 4/12, simple + composite glyphs, advance widths),
an anti-aliased nonzero-winding polygon rasterizer (4 vertical sub-scanlines, exact horizontal span coverage), a few
vector primitives (rounded rectangles, rings, polygons, lines, arrows) and an RGB/RGBA PNG encoder. Fonts are read as
data from paths given by the caller (e.g. IBM Plex, SIL OFL); no font files are bundled.
"""

from __future__ import annotations

import math
import struct
import zlib


# ---------------------------------------------------------------------------------------------------------
# TrueType reader
class TTF:
    def __init__(self, path: str):
        b = open(path, "rb").read()
        self.b = b
        n = struct.unpack(">H", b[4:6])[0]
        self.t = {}
        for i in range(n):
            tag, _chk, off, ln = struct.unpack(">4sIII", b[12 + 16 * i:28 + 16 * i])
            self.t[tag.decode("latin1")] = (off, ln)
        head = self.t["head"][0]
        self.upem = struct.unpack(">H", b[head + 18:head + 20])[0]
        self.loc_long = struct.unpack(">h", b[head + 50:head + 52])[0] == 1
        self.num_glyphs = struct.unpack(">H", b[self.t["maxp"][0] + 4:self.t["maxp"][0] + 6])[0]
        hh = self.t["hhea"][0]
        self.ascender, self.descender = struct.unpack(">hh", b[hh + 4:hh + 8])
        self.n_hmetrics = struct.unpack(">H", b[hh + 34:hh + 36])[0]
        self._cmap = self._read_cmap()
        self._cache = {}

    def _u16(self, o):
        return struct.unpack(">H", self.b[o:o + 2])[0]

    def _i16(self, o):
        return struct.unpack(">h", self.b[o:o + 2])[0]

    def _read_cmap(self):
        base = self.t["cmap"][0]
        n = self._u16(base + 2)
        subs = {}
        for i in range(n):
            pid, eid, off = struct.unpack(">HHI", self.b[base + 4 + 8 * i:base + 12 + 8 * i])
            subs[(pid, eid)] = base + off
        for key in ((3, 10), (0, 4), (3, 1), (0, 3)):
            if key in subs:
                o = subs[key]
                fmt = self._u16(o)
                if fmt == 12:
                    groups = struct.unpack(">I", self.b[o + 12:o + 16])[0]
                    m = {}
                    for g in range(groups):
                        s, e, gid = struct.unpack(">III", self.b[o + 16 + 12 * g:o + 28 + 12 * g])
                        for cp in range(s, e + 1):
                            m[cp] = gid + cp - s
                    return m
                if fmt == 4:
                    seg2 = self._u16(o + 6)
                    ends = o + 14
                    starts = ends + seg2 + 2
                    deltas = starts + seg2
                    ranges = deltas + seg2
                    m = {}
                    for s in range(seg2 // 2):
                        end, start = self._u16(ends + 2 * s), self._u16(starts + 2 * s)
                        delta, ro = self._i16(deltas + 2 * s), self._u16(ranges + 2 * s)
                        for cp in range(start, end + 1):
                            if cp == 0xFFFF:
                                continue
                            if ro == 0:
                                gid = (cp + delta) & 0xFFFF
                            else:
                                gid = self._u16(ranges + 2 * s + ro + 2 * (cp - start))
                                gid = (gid + delta) & 0xFFFF if gid else 0
                            m[cp] = gid
                    return m
        raise ValueError("no supported cmap subtable")

    def gid(self, ch: str) -> int:
        return self._cmap.get(ord(ch), 0)

    def advance(self, gid: int) -> int:
        h = self.t["hmtx"][0]
        i = min(gid, self.n_hmetrics - 1)
        return self._u16(h + 4 * i)

    def _glyph_off(self, gid):
        loca = self.t["loca"][0]
        if self.loc_long:
            a, b = struct.unpack(">II", self.b[loca + 4 * gid:loca + 4 * gid + 8])
        else:
            a, b = (x * 2 for x in struct.unpack(">HH", self.b[loca + 2 * gid:loca + 2 * gid + 4]))
        return self.t["glyf"][0] + a, b - a

    def contours(self, gid: int, depth=0):
        """List of contours; each contour is a list of (x, y, on_curve) in font units."""
        if gid in self._cache:
            return self._cache[gid]
        off, ln = self._glyph_off(gid)
        if ln == 0:
            self._cache[gid] = []
            return []
        nc = self._i16(off)
        out = []
        if nc >= 0:
            ends = [self._u16(off + 10 + 2 * i) for i in range(nc)]
            p = off + 10 + 2 * nc
            p += 2 + self._u16(p)
            npts = ends[-1] + 1 if ends else 0
            flags = []
            while len(flags) < npts:
                f = self.b[p]
                p += 1
                flags.append(f)
                if f & 8:
                    r = self.b[p]
                    p += 1
                    flags.extend([f] * r)
            xs, x = [], 0
            for f in flags:
                if f & 2:
                    d = self.b[p]
                    p += 1
                    x += d if f & 16 else -d
                elif not f & 16:
                    x += self._i16(p)
                    p += 2
                xs.append(x)
            ys, y = [], 0
            for f in flags:
                if f & 4:
                    d = self.b[p]
                    p += 1
                    y += d if f & 32 else -d
                elif not f & 32:
                    y += self._i16(p)
                    p += 2
                ys.append(y)
            s = 0
            for e in ends:
                out.append([(xs[i], ys[i], bool(flags[i] & 1)) for i in range(s, e + 1)])
                s = e + 1
        elif depth < 8:
            p = off + 10
            while True:
                fl, cg = self._u16(p), self._u16(p + 2)
                p += 4
                if fl & 1:
                    a1, a2 = self._i16(p), self._i16(p + 2)
                    p += 4
                else:
                    a1, a2 = struct.unpack(">bb", self.b[p:p + 2])
                    p += 2
                dx, dy = (a1, a2) if fl & 2 else (0, 0)
                sa, sb, sc, sd = 1.0, 0.0, 0.0, 1.0
                f2 = lambda o: self._i16(o) / 16384.0
                if fl & 8:
                    sa = sd = f2(p)
                    p += 2
                elif fl & 0x40:
                    sa, sd = f2(p), f2(p + 2)
                    p += 4
                elif fl & 0x80:
                    sa, sb, sc, sd = f2(p), f2(p + 2), f2(p + 4), f2(p + 6)
                    p += 8
                for ct in self.contours(cg, depth + 1):
                    out.append([(sa * x + sc * y + dx, sb * x + sd * y + dy, on) for x, y, on in ct])
                if not fl & 0x20:
                    break
        self._cache[gid] = out
        return out


def contour_to_polyline(ct, tx, steps=6):
    """Quadratic TrueType contour -> closed polyline in pixel space; tx maps font units to pixels."""
    n = len(ct)
    if n < 2:
        return []
    pts = [(tx(x, y), on) for x, y, on in ct]
    # start on an on-curve point (or the midpoint of two off-curve points)
    k = next((i for i in range(n) if pts[i][1]), None)
    if k is None:
        a, b = pts[0][0], pts[-1][0]
        start = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        seq = [(p, on) for p, on in pts]
    else:
        start = pts[k][0]
        seq = pts[k + 1:] + pts[:k]
    poly, cur, ctrl = [start], start, None
    for p, on in seq + [(start, True)]:
        if on:
            if ctrl is None:
                poly.append(p)
            else:
                for i in range(1, steps + 1):
                    t = i / steps
                    poly.append(((1 - t) ** 2 * cur[0] + 2 * (1 - t) * t * ctrl[0] + t * t * p[0],
                                 (1 - t) ** 2 * cur[1] + 2 * (1 - t) * t * ctrl[1] + t * t * p[1]))
                ctrl = None
            cur = p
        else:
            if ctrl is not None:
                mid = ((ctrl[0] + p[0]) / 2, (ctrl[1] + p[1]) / 2)
                for i in range(1, steps + 1):
                    t = i / steps
                    poly.append(((1 - t) ** 2 * cur[0] + 2 * (1 - t) * t * ctrl[0] + t * t * mid[0],
                                 (1 - t) ** 2 * cur[1] + 2 * (1 - t) * t * ctrl[1] + t * t * mid[1]))
                cur = mid
            ctrl = p
    return poly


# ---------------------------------------------------------------------------------------------------------
# canvas + rasterizer
def hex_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class Canvas:
    def __init__(self, w, h, bg="#000000", alpha=False):
        self.w, self.h, self.alpha = w, h, alpha
        r, g, b = hex_rgb(bg)
        self.px = bytearray(bytes((r, g, b, 255 if not alpha else 0)) * (w * h)) if alpha else bytearray(bytes((r, g, b)) * (w * h))
        self.ch = 4 if alpha else 3

    def blend(self, x, y, rgb, a):
        if a <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        a = min(a, 1.0)
        i = (y * self.w + x) * self.ch
        p = self.px
        if self.alpha:
            da = p[i + 3] / 255.0
            oa = a + da * (1 - a)
            if oa <= 0:
                return
            for k in range(3):
                p[i + k] = int(round((rgb[k] * a + p[i + k] * da * (1 - a)) / oa))
            p[i + 3] = int(round(oa * 255))
        else:
            for k in range(3):
                p[i + k] = int(round(rgb[k] * a + p[i + k] * (1 - a)))

    def fill_polys(self, polys, color, opacity=1.0, ss=4):
        """Fill closed polylines with the nonzero winding rule, anti-aliased."""
        rgb = color if isinstance(color, tuple) else hex_rgb(color)
        edges = []
        for poly in polys:
            for i in range(len(poly)):
                x0, y0 = poly[i]
                x1, y1 = poly[(i + 1) % len(poly)]
                if y0 != y1:
                    edges.append((x0, y0, x1, y1, 1 if y1 > y0 else -1))
        if not edges:
            return
        ymin = max(0, int(math.floor(min(min(e[1], e[3]) for e in edges))))
        ymax = min(self.h - 1, int(math.ceil(max(max(e[1], e[3]) for e in edges))))
        xmin = max(0, int(math.floor(min(min(e[0], e[2]) for e in edges))))
        xmax = min(self.w - 1, int(math.ceil(max(max(e[0], e[2]) for e in edges))))
        width = xmax - xmin + 2
        for y in range(ymin, ymax + 1):
            cov = [0.0] * width
            for s in range(ss):
                sy = y + (s + 0.5) / ss
                xs = []
                for x0, y0, x1, y1, d in edges:
                    lo, hi = (y0, y1) if y0 < y1 else (y1, y0)
                    if lo <= sy < hi:
                        xs.append((x0 + (sy - y0) * (x1 - x0) / (y1 - y0), d))
                if not xs:
                    continue
                xs.sort()
                wnd = 0
                for j in range(len(xs) - 1):
                    wnd += xs[j][1]
                    if wnd == 0:
                        continue
                    a, b = xs[j][0] - xmin, xs[j + 1][0] - xmin
                    if b <= a:
                        continue
                    a, b = max(a, 0.0), min(b, width - 1.0)
                    ia, ib = int(a), int(b)
                    if ia == ib:
                        cov[ia] += (b - a) / ss
                    else:
                        cov[ia] += (ia + 1 - a) / ss
                        for k in range(ia + 1, ib):
                            cov[k] += 1.0 / ss
                        cov[ib] += (b - ib) / ss
            for k, c in enumerate(cov):
                if c > 0.002:
                    self.blend(xmin + k, y, rgb, c * opacity)

    # -- text ------------------------------------------------------------------------------------------
    def text(self, font: TTF, s: str, x, baseline, size, color, tracking=0.0, opacity=1.0):
        sc = size / font.upem
        pen = x
        polys = []
        for ch in s:
            g = font.gid(ch)
            for ct in font.contours(g):
                poly = contour_to_polyline(ct, lambda fx, fy, p=pen: (p + fx * sc, baseline - fy * sc))
                if len(poly) > 2:
                    polys.append(poly)
            pen += font.advance(g) * sc + tracking
        self.fill_polys(polys, color, opacity)
        return pen - x

    # -- shapes ----------------------------------------------------------------------------------------
    def rect(self, x0, y0, x1, y1, color, opacity=1.0):
        self.fill_polys([[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]], color, opacity)

    def rounded(self, x0, y0, x1, y1, r, color, opacity=1.0, border=None, bw=0.0):
        self.fill_polys([rounded_rect(x0, y0, x1, y1, r)], color, opacity)
        if border and bw > 0:
            outer = rounded_rect(x0, y0, x1, y1, r)
            inner = list(reversed(rounded_rect(x0 + bw, y0 + bw, x1 - bw, y1 - bw, max(r - bw, 0.5))))
            self.fill_polys([outer, inner], border, 1.0)

    def circle(self, cx, cy, r, color, opacity=1.0, n=48):
        self.fill_polys([[(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]],
                        color, opacity)

    def line(self, x0, y0, x1, y1, w, color, opacity=1.0):
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L * w / 2, dx / L * w / 2
        self.fill_polys([[(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)]], color, opacity)

    def arrow(self, x0, y, x1, color, w=3.0, head=12.0):
        self.line(x0, y, x1 - head * 0.8, y, w, color)
        self.fill_polys([[(x1, y), (x1 - head, y - head * 0.6), (x1 - head, y + head * 0.6)]], color)


def rounded_rect(x0, y0, x1, y1, r, n=10):
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def measure(font: TTF, s: str, size, tracking=0.0) -> float:
    sc = size / font.upem
    return sum(font.advance(font.gid(ch)) * sc + tracking for ch in s)


def wrap(font: TTF, s: str, size, max_w) -> list:
    words, lines, cur = s.split(" "), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if measure(font, t, size) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------------------------------------------------
def write_png(path: str, cv: Canvas):
    ch = cv.ch
    stride = cv.w * ch
    raw = bytearray()
    prev = bytes(stride)
    for y in range(cv.h):
        row = bytes(cv.px[y * stride:(y + 1) * stride])
        sub = bytes((row[i] - (row[i - ch] if i >= ch else 0)) & 0xFF for i in range(stride))   # filter 1 (Sub)
        raw += b"\x01" + sub
        prev = row
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", cv.w, cv.h, 8, 6 if cv.alpha else 2, 0, 0, 0)) \
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)
    return len(png)
