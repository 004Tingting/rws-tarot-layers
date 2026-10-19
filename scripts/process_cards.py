"""RWS tarot card layout analysis & 3-layer split (edge / artwork / title).

Subcommands:
  analyze [CARD...]      print detected geometry for given card names (default: The Fool)
  analyze-all            run analyze over all 22 majors, print consistency table
  boxes CARD OUT         save an annotated PNG (red=edge, yellow=artwork, green=title) for eyeballing
  split                  split all 22 majors into 3 RGBA layers + recomposite check
  split-minors           split all 56 minors
  preview-assets         generate downscaled layer copies for preview.html

Layer model (Atropos game-box convention, matches the user's red/yellow/green boxes):
  edge    (z=0, 牌边缘): white margin + frame lines + title-band background (text inpainted away);
          transparent window where the artwork sits (window smaller than artwork rect so the
          artwork tucks under the frame and parallax never exposes gaps).
  artwork (z<0, 牌面): opaque rectangle crop placed BEHIND the edge layer.
  title   (z>0, 牌标题): the printed caption text only (alpha from darkness), floats ABOVE;
          its background belongs to the edge layer per user spec.
All layers are full-canvas 2100x3600 RGBA PNGs so they stack with inset:0 + translateZ.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
CARDS = HERE / "cards"
OUT = HERE / "processed"

# ---- card name tables ------------------------------------------------------

MAJORS = [  # (RWS number, slug, Commons file base name)
    (0, "the-fool", "The Fool"),
    (1, "the-magician", "The Magician"),
    (2, "the-high-priestess", "The High Priestess"),
    (3, "the-empress", "The Empress"),
    (4, "the-emperor", "The Emperor"),
    (5, "the-hierophant", "The Hierophant"),
    (6, "the-lovers", "The Lovers"),
    (7, "the-chariot", "The Chariot"),
    (8, "strength", "Strength"),
    (9, "the-hermit", "The Hermit"),
    (10, "wheel-of-fortune", "Wheel of Fortune"),
    (11, "justice", "Justice"),
    (12, "the-hanged-man", "The Hanged Man"),
    (13, "death", "Death"),
    (14, "temperance", "Temperance"),
    (15, "the-devil", "The Devil"),
    (16, "the-tower", "The Tower"),
    (17, "the-star", "The Star"),
    (18, "the-moon", "The Moon"),
    (19, "the-sun", "The Sun"),
    (20, "judgement", "Judgement"),
    (21, "the-world", "The World"),
]

MINOR_RANKS = ["ace", "two", "three", "four", "five", "six", "seven", "eight",
               "nine", "ten", "page", "knight", "queen", "king"]
MINOR_SUITS = ["wands", "cups", "swords", "pentacles"]

SUFFIX = "(Rider-Waite Smith tarot deck).png"

# ---- geometry detection ----------------------------------------------------

def card_path(base: str) -> Path:
    return CARDS / f"{base} {SUFFIX}"


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Contiguous True runs of a 1-D boolean array as (start, end_excl)."""
    m = mask.astype(np.int8)
    d = np.diff(m)
    starts = list(np.where(d == 1)[0] + 1)
    ends = list(np.where(d == -1)[0] + 1)
    if m[0]:
        starts = [0] + starts
    if m[-1]:
        ends = ends + [len(m)]
    return list(zip(starts, ends))


def _numeral_chip(stripL: np.ndarray):
    """Find the Roman-numeral chip in a template-slot strip (HxW luminance).

    Connected-component analysis on BOTH polarity masks at several thresholds
    (scene dominance can bias a global median, e.g. a dark sky on a bright
    print): glyph characters of one numeral share rows (vertical overlap
    >=65%, tops within 14px) and sit close (disjoint columns, gap <=32px),
    grouping into a chip 40-460px wide, 90-165px tall. Numerals are visually
    centred (<=120px off centre). The winning chip is then trimmed against
    the mask: rows/cols whose glyph-pixel coverage is negligible (scene ink
    below the serifs, side edges) are cut away, so ONLY the numeral remains.
    Returns (group=(r0, r1, c0, c1), polarity) or (None, polarity).
    """
    m = float(np.median(stripL))
    ccentre = stripL.shape[1] // 2
    best = None
    for polarity, delta in (("dark", 70.0), ("dark", 90.0), ("dark", 110.0),
                            ("dark", 130.0), ("light", 70.0), ("light", 90.0),
                            ("light", 110.0)):
        mask = (stripL < max(90.0, m - delta) if polarity == "dark"
                else stripL > m + delta)
        lab, n = ndimage.label(mask, structure=np.ones((3, 3), bool))
        if n == 0:
            continue
        comps = []
        for sl in ndimage.find_objects(lab):
            h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
            if h >= 30 and w >= 8:  # skip specks and line fragments
                comps.append([sl[0].start, sl[0].stop, sl[1].start, sl[1].stop])
        comps.sort(key=lambda c: c[0])
        groups = []
        for c in comps:
            hit = None
            for g in groups:
                ov = min(c[1], g[1]) - max(c[0], g[0])
                gap = max(c[2], g[2]) - min(c[3], g[3])
                # one numeral's chars: same rows, disjoint close columns
                if (ov > 0.65 * min(c[1] - c[0], g[1] - g[0])
                        and abs(c[0] - g[0]) <= 14 and 0 < gap <= 32):
                    hit = g
                    break
            if hit is not None:
                hit[0] = min(hit[0], c[0]); hit[1] = max(hit[1], c[1])
                hit[2] = min(hit[2], c[2]); hit[3] = max(hit[3], c[3])
            else:
                groups.append(c)
        cands = [g for g in groups
                 if 90 <= g[1] - g[0] <= 165 and 40 <= g[3] - g[2] <= 460]
        # numerals connected to scene art below them come out too tall; the
        # print always places the chip at the top of such a blob — trim to the
        # top 150 rows
        for g in groups:
            if 165 < g[1] - g[0] <= 260 and 40 <= g[3] - g[2] <= 460:
                cands.append([g[0], g[0] + 150, g[2], g[3]])
        if not cands:
            continue
        # numerals are visually centred; scene fragments off-centre lose
        cands = [g for g in cands
                 if abs((g[2] + g[3]) // 2 - ccentre) <= 120]
        if not cands:
            continue
        g = min(cands, key=lambda g: abs((g[2] + g[3]) // 2 - ccentre))
        d = abs((g[2] + g[3]) // 2 - ccentre)
        # coverage trim: drop edge rows/cols that carry almost no glyph pixels
        sub = mask[g[0]:g[1], g[2]:g[3]]
        rowc = sub.mean(axis=1)
        colc = sub.mean(axis=0)
        h0 = 0
        while h0 < len(rowc) - 60 and rowc[h0] < 0.18:
            h0 += 1
        h1 = len(rowc)
        while h1 > 60 and rowc[h1 - 1] < 0.18:
            h1 -= 1
        # main band: rows carrying real strokes (serifs/strokes >=30% width);
        # anything hanging below the serif line (hair, rays, vines) drops out
        main = np.where(rowc[h0:h1] >= 0.30)[0]
        if len(main) >= 40:
            h1 = h0 + int(main[-1]) + 1
        w0 = 0
        while w0 < len(colc) - 30 and colc[w0] < 0.18:
            w0 += 1
        w1 = len(colc)
        while w1 > 30 and colc[w1 - 1] < 0.18:
            w1 -= 1
        if h1 - h0 >= 60 and w1 - w0 >= 30:
            g = [g[0] + h0, g[0] + h1, g[2] + w0, g[2] + w1]
        if best is None or d < best[0]:
            best = (d, g, polarity)
    if best is None:
        return None, "dark"
    return best[1], best[2]


def detect_geometry(img: np.ndarray, numeral: bool = True) -> dict:
    """Detect printed bbox, frame lines, artwork rect, band rect, title text bbox.

    Structure of every RWS card in this scan: white margin -> full-width dark
    frame line (top/left/right/bottom) -> artwork -> full-width dark separator
    line -> title band (light ground + dark caption) -> bottom frame line.
    The band is found STRUCTURALLY (between two full-width dark lines near the
    bottom), not by colour thresholds.
    Rects are (row_top, row_bottom_excl, col_left, col_right_excl).
    """
    L = (0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2])
    H, W = L.shape
    ink = L < 232

    # 1) printed bbox: outermost frame lines span (nearly) the full card
    row_ink = ink.sum(axis=1)
    col_ink = ink.sum(axis=0)
    rows = np.where(row_ink > W * 0.5)[0]
    cols = np.where(col_ink > H * 0.5)[0]
    if len(rows) == 0 or len(cols) == 0:
        raise ValueError("frame lines not found")
    top, bottom = int(rows[0]), int(rows[-1]) + 1
    left, right = int(cols[0]), int(cols[-1]) + 1

    # 2) frame line runs (near-full-width dark rows / near-full-height dark cols)
    dark_row = (L[:, left + 60:right - 60] < 130).mean(axis=1)
    dark_col = (L[top + 60:bottom - 60, :] < 130).mean(axis=0)
    r_runs = _runs(dark_row > 0.9)
    c_runs = _runs(dark_col > 0.9)
    # frame lines are ~10-20px of ink; on cards with a very dark artwork sky
    # the line merges with the scene into one long dark run — fall back to the
    # standard frame thickness there
    top_line = next(r for r in r_runs if r[0] <= top + 40)
    bottom_line = next(r for r in reversed(r_runs) if r[1] >= bottom - 40)
    left_line = next(c for c in c_runs if c[0] <= left + 40)
    right_line = next(c for c in reversed(c_runs) if c[1] >= right - 40)
    _edge = lambda run, axis_max: run[0] + (run[1] - run[0]
                                            if run[1] - run[0] <= 40 else 22)
    inner_top = _edge(top_line, None)
    inner_left = _edge(left_line, None)
    inner_right = right_line[0] if right_line[1] - right_line[0] <= 40 \
        else right_line[1] - 22
    inner_bottom = bottom_line[0] if bottom_line[1] - bottom_line[0] <= 40 \
        else bottom_line[1] - 22

    # 3) title band: majors and court cards carry a caption band framed by a
    #    full-width dark separator line above it; pip cards (2-10) in this
    #    print have NO band and NO caption — artwork runs to the bottom frame.
    seps = [r for r in r_runs if inner_bottom - 500 < r[1] <= inner_bottom - 150]
    band = text_bbox = band_bg = None
    sep = (inner_bottom, inner_bottom)
    if seps:
        cand = seps[-1]
        cand_band = (cand[1], inner_bottom, inner_left, inner_right)
        ERODE = 16
        interior = L[cand_band[0] + ERODE:cand_band[1] - ERODE,
                     cand_band[2] + ERODE:cand_band[3] - ERODE]
        bg = float(np.median(interior))
        tm = interior < bg - 45
        trows = np.where(tm.sum(axis=1) >= 25)[0]
        tcols = np.where(tm.sum(axis=0) >= 25)[0]
        # a caption spans most of the band, centred; a lone artist signature
        # (bottom-right corner of some cards) is small and off-centre — both
        # must hold, else this is no caption band at all
        caption = (len(trows) and len(tcols)
                   and (tcols[-1] - tcols[0]) >= 0.45 * interior.shape[1]
                   and abs((tcols[0] + tcols[-1]) // 2 - interior.shape[1] // 2)
                   <= 0.18 * interior.shape[1])
        if caption:
            band = cand_band
            sep = cand
            text_bbox = (int(band[0] + ERODE + trows[0]) - 6,
                         int(band[0] + ERODE + trows[-1]) + 1 + 6,
                         int(band[2] + ERODE + tcols[0]) - 8,
                         int(band[2] + ERODE + tcols[-1]) + 1 + 8)
            band_bg = bg

    # 4) artwork rect tucks 8px UNDER the frame lines (and under the band
    #    separator when present); pip artwork runs to the bottom frame
    UNDER = 8
    artwork = (inner_top - UNDER, sep[0] + UNDER, inner_left - UNDER, inner_right + UNDER)
    hole = (inner_top, sep[0], inner_left, inner_right)

    # 6) numeral: Roman numerals (I..XXI) or 0, printed top-centre in a fixed
    #    template slot (glyph height 110-140px). Connected-component grouping
    #    (see _numeral_chip) picks the compact chip nearest centre; scene ink
    #    (clouds, veils, tables, ropes) is taller/wider or off-centre. Aces and
    #    courts have no numeral — detection returns None and the numeral stays
    #    in the artwork (graceful degrade).
    num_bbox = num_bg = None
    num_donor = None
    num_polarity = "dark"
    if numeral:
        try:
            strip_t = inner_top + 10
            strip_b = min(inner_top + 246, sep[0] - 20)  # template slot rows
            centre = (inner_left + inner_right) // 2
            x0 = max(inner_left + 20, centre - 330)
            x1 = min(inner_right - 20, centre + 330)
            g_chip, num_polarity = _numeral_chip(L[strip_t:strip_b, x0:x1])
            if g_chip is not None:
                num_bbox = (int(strip_t + g_chip[0]) - 6,
                            int(strip_t + g_chip[1]) + 7,
                            int(x0 + g_chip[2]) - 8, int(x0 + g_chip[3]) + 8)
                # ground level comes from the CLEAN donor patch (a bbox median
                # would be dragged dark by the very glyphs we're masking)
                bounds = (inner_top + 4, sep[0] - 4, inner_left + 4, inner_right - 4)
                _which, num_donor = _pick_donor(L, num_bbox, bounds, 0.0)
                d0, d1, dc0, dc1 = num_donor
                num_bg = float(np.median(L[d0:d1, dc0:dc1]))
                num_donor = [int(v) for v in num_donor]
                # polarity re-check from bbox content: the winning mask's
                # global threshold can disagree with the local ground (e.g.
                # light glyphs on a black sky picked up as dark hatching)
                Lb = L[num_bbox[0]:num_bbox[1], num_bbox[2]:num_bbox[3]]
                n_dark = int((Lb < num_bg - 70).sum())
                n_light = int((Lb > num_bg + 70).sum())
                num_polarity = "dark" if n_dark >= n_light else "light"
        except (ValueError, IndexError):  # noqa: BLE001 - degrade, don't fail
            num_bbox = num_bg = None

    return {
        "printed": [top, bottom, left, right],
        "frame_lines": {"top": [int(top_line[0]), int(top_line[1])],
                        "bottom": [int(bottom_line[0]), int(bottom_line[1])],
                        "left": [int(left_line[0]), int(left_line[1])],
                        "right": [int(right_line[0]), int(right_line[1])]},
        "separator": [int(sep[0]), int(sep[1])],
        "band": [int(v) for v in band] if band is not None else None,
        "band_bg": band_bg,
        "text_bbox": [int(v) for v in text_bbox] if text_bbox is not None else None,
        "artwork_rect": [int(v) for v in artwork],
        "edge_hole": [int(v) for v in hole],
        "num_bbox": [int(v) for v in num_bbox] if num_bbox is not None else None,
        "num_bg": num_bg,
        "num_polarity": num_polarity,
        "num_donor": num_donor,
        "inner": [int(inner_top), int(inner_bottom), int(inner_left), int(inner_right)],
    }


def load_card(base: str, numeral: bool = True) -> tuple[np.ndarray, dict]:
    img = np.asarray(Image.open(card_path(base)).convert("RGB"))
    return img, detect_geometry(img, numeral=numeral)


# ---- subcommands ------------------------------------------------------------

def cmd_analyze(names):
    for base in names:
        img, g = load_card(base)
        p, b, t, a = g["printed"], g["band"], g["text_bbox"], g["artwork_rect"]
        print(f"{base}:")
        print(f"  printed bbox   {p}  (H={p[1]-p[0]} W={p[3]-p[2]})")
        print(f"  inner (frame)  {g['inner']}  separator line {g['separator']}")
        print(f"  band rows      {b[0]}..{b[1]} (h={b[1]-b[0]})  full width cols {b[2]}..{b[3]}")
        print(f"  text bbox      {t}  (h={t[1]-t[0]} w={t[3]-t[2]})")
        print(f"  artwork rect   {a}  (h={a[1]-a[0]} w={a[3]-a[2]})")


def cmd_analyze_all():
    print(f"{'card':<20}{'printed(top,bot,left,right)':<30}{'band rows':<16}"
          f"{'band h':<8}{'text h':<8}{'sep':<12}{'art h':<7}")
    stats = []
    for n, slug, base in MAJORS:
        _, g = load_card(base)
        p, b, t = g["printed"], g["band"], g["text_bbox"]
        a = g["artwork_rect"]
        print(f"{base:<20}{str(p):<30}{f'{b[0]}..{b[1]}':<16}{b[1]-b[0]:<8}"
              f"{t[1]-t[0]:<8}{str(g['separator']):<12}{a[1]-a[0]:<7}")
        stats.append(g)
    arr = lambda k: np.array([s[k] for s in stats])
    for k in ("printed", "band", "text_bbox", "artwork_rect", "edge_hole", "separator"):
        v = arr(k)
        print(f"{k:<14} max-deviation from median: {np.abs(v - np.median(v, axis=0)).max(axis=0)}")


def cmd_boxes(base, out):
    from PIL import ImageDraw
    img, g = load_card(base)
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)
    rect = lambda r: [r[2], r[0], r[3] - 1, r[1] - 1]  # (t,b,l,r) -> PIL (x0,y0,x1,y1)
    d.rectangle(rect(g["printed"]), outline=(255, 0, 0), width=6)          # red: edge scope
    a = g["artwork_rect"]
    d.rectangle(rect(a), outline=(255, 200, 0), width=6)                   # yellow: artwork
    t = g["text_bbox"]
    d.rectangle(rect(t), outline=(0, 200, 0), width=6)                     # green: title
    im.save(out)
    print(f"saved {out}")


def cmd_split(names):
    majors = MAJORS if not names else [m for m in MAJORS if m[2] in names]
    OUT.mkdir(exist_ok=True)
    report = {}
    for n, slug, base in majors:
        try:
            img, g = load_card(base, numeral=True)
            if g.get("num_bbox") is None:
                print(f"[{n:02d} {slug}] WARNING: no numeral detected", flush=True)
            layers = build_layers(img, g)
        except Exception as e:  # noqa: BLE001 - keep the batch running
            print(f"[{n:02d} {slug}] FAILED: {e}", flush=True)
            report[base] = {"number": n, "slug": slug, "error": str(e)}
            continue
        outdir = OUT / "major-arcana" / f"{n:02d}-{slug}"
        outdir.mkdir(parents=True, exist_ok=True)
        for name, arr in layers.items():
            Image.fromarray(arr).save(outdir / f"{name}.png", optimize=True)
        diff = recomposite_check(img, g, layers)
        report[base] = {"number": n, "slug": slug, "geometry": g, "check": diff}
        print(f"[{n:02d} {slug}] recomposite: mean={diff['mean']:.3f} "
              f"max={diff['max']} >8: {diff['gt8_ppm']:.1f} ppm", flush=True)
    path = OUT / "major-arcana" / "layout.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    old.update(report)
    path.write_text(json.dumps(old, indent=1), encoding="utf-8")


def cmd_proof(base, out):
    """Side-by-side proof sheet: original / recomposite / edge / artwork / title."""
    img, g = load_card(base)
    layers = build_layers(img, g)

    def over_white(rgba):
        a = rgba[:, :, 3:4].astype(np.float32) / 255
        return (rgba[:, :, :3] * a + 255 * (1 - a)).astype(np.uint8)

    def over_bg(rgba, bg_rgb):
        a = rgba[:, :, 3:4].astype(np.float32) / 255
        return (rgba[:, :, :3] * a + np.array(bg_rgb) * (1 - a)).astype(np.uint8)

    comp = recomposite(img, g, layers)
    bg_rgb = band_bg_rgb(img, g)
    nb = g["num_bbox"]
    num_rgb = tuple(int(v) for v in np.median(
        img[nb[0]:nb[1], nb[2]:nb[3]].reshape(-1, 3), axis=0))
    panels = [
        ("original", img),
        ("recomposite", comp),
        ("edge (on white)", over_white(layers["edge"])),
        ("artwork (numeral inpainted)", over_white(layers["artwork"])),
        ("title (on band bg)", over_bg(layers["title"], bg_rgb)),
        ("number (on sky bg)", over_bg(layers["number"], num_rgb)),
    ]
    PW = 560
    ph = int(PW * img.shape[0] / img.shape[1])
    LABEL = 34
    sheet = Image.new("RGB", (PW * 2 + 30, (ph + LABEL) * 3 + 40), (34, 34, 34))
    from PIL import ImageDraw
    d = ImageDraw.Draw(sheet)
    for i, (label, arr) in enumerate(panels):
        im = Image.fromarray(arr).resize((PW, ph), Image.LANCZOS)
        x = 10 + (i % 2) * (PW + 10)
        y = 10 + (i // 2) * (ph + LABEL + 10)
        sheet.paste(im, (x, y + LABEL))
        d.text((x + 4, y + 8), label, fill=(240, 240, 240))
    sheet.save(out, optimize=True)
    print(f"saved {out}")


def cmd_split_minors():
    report = {}
    count = fails = 0
    for suit in MINOR_SUITS:
        for rank_n, rank in enumerate(MINOR_RANKS, 1):
            cands = [f"{rank.capitalize()} of {suit.capitalize()}"]
            if rank == "ace":  # Commons naming quirk in this scan set
                cands.append(f"One of {suit.capitalize()}")
            path = next((p for p in (card_path(c) for c in cands) if p.exists()), None)
            if path is None:
                print(f"MISSING: {cands[0]}", flush=True)
                fails += 1
                continue
            base = next(c for c in cands if card_path(c) == path)
            try:
                # pips 2-10 carry a top Roman numeral; aces and courts have
                # none — skip detection there entirely (a "chip" on a court
                # card is always a crown/hat false positive)
                img, g = load_card(base, numeral=(rank_n <= 10))
                if g.get("num_bbox") is None and 2 <= rank_n <= 10:
                    print(f"[{suit} {rank_n:02d}] WARNING: no numeral detected",
                          flush=True)
                layers = build_layers(img, g)
            except Exception as e:  # noqa: BLE001 - keep the batch running
                print(f"[{suit} {rank_n:02d}] FAILED: {e}", flush=True)
                report[base] = {"suit": suit, "rank": rank, "rank_number": rank_n,
                                "error": str(e)}
                fails += 1
                continue
            outdir = OUT / "minor-arcana" / suit / f"{rank_n:02d}-{base.lower().replace(' ', '-')}"
            outdir.mkdir(parents=True, exist_ok=True)
            for name, arr in layers.items():
                Image.fromarray(arr).save(outdir / f"{name}.png", optimize=True)
            diff = recomposite_check(img, g, layers)
            report[base] = {"suit": suit, "rank": rank, "rank_number": rank_n,
                            "geometry": g, "check": diff}
            count += 1
            print(f"[{suit} {rank_n:02d}] recomposite: mean={diff['mean']:.3f} "
                  f"max={diff['max']} >8: {diff['gt8_ppm']:.1f} ppm", flush=True)
    (OUT / "minor-arcana" / "layout.json").write_text(
        json.dumps(report, indent=1), encoding="utf-8")
    print(f"split {count} minors, {fails} failures", flush=True)


# ---- layer construction -----------------------------------------------------

def _box_blur(a: np.ndarray, r: int) -> np.ndarray:
    """Separable box blur of HxWx3 float32 via cumsum (edge-padded)."""
    c = np.cumsum(np.pad(a, ((r + 1, r), (0, 0), (0, 0)), mode="edge"), axis=0)
    v = (c[2 * r + 1:] - c[:-2 * r - 1]) / (2 * r + 1)
    c = np.cumsum(np.pad(v, ((0, 0), (r + 1, r), (0, 0)), mode="edge"), axis=1)
    return (c[:, 2 * r + 1:] - c[:, :-2 * r - 1]) / (2 * r + 1)


def _glyph_alpha(L_patch: np.ndarray, bg: float, polarity: str = "dark") -> np.ndarray:
    """Glyph alpha vs the local ground level (either polarity), despeckled.

    The ramp starts at bg-40 (dark) / bg+40 (light) so anti-aliased glyph
    fringes get partial alpha — a steeper cut leaves halo residue in the
    artwork once the glyphs are lifted out.
    """
    if polarity == "dark":
        alpha = np.clip((bg - 40.0 - L_patch) / 25.0, 0.0, 1.0)
    else:  # light glyphs on a dark ground
        alpha = np.clip((L_patch - (bg + 40.0)) / 25.0, 0.0, 1.0)
    m = alpha > 0  # drop isolated pixels (<3 live neighbours in 3x3)
    nb = sum(np.roll(np.roll(m, i, 0), j, 1)
             for i in (-1, 0, 1) for j in (-1, 0, 1) if (i, j) != (0, 0))
    alpha[m & (nb < 3)] = 0
    return alpha


def _dilate(m: np.ndarray, r: int) -> np.ndarray:
    out = m.copy()
    for i in range(-r, r + 1):
        for j in range(-r, r + 1):
            out |= np.roll(np.roll(m, i, 0), j, 1)
    return out


def vfill_inpaint(img: np.ndarray, bbox, mask: np.ndarray, donor) -> np.ndarray:
    """Numeral repair: vertical interpolation between the clean paper above and
    below each masked column span, plus weave texture from the donor patch.

    A per-row/low-frequency synthesis gets dragged dark by the glyphs' ink
    halo; interpolating the actual neighbouring ground matches the local paper
    colour exactly (numerals sit on flat ground). Returns HxWx3 patch.
    """
    r0, r1, c0, c1 = bbox
    h, w = r1 - r0, c1 - c0
    region = img[r0:r1, c0:c1].astype(np.float32)
    fill = region.copy()
    ys = np.arange(h)[:, None]
    first = np.where(mask, ys, h).min(axis=0)   # first masked row per column
    last = np.where(mask, ys, -1).max(axis=0)   # last masked row per column
    for x in range(w):
        if not mask[:, x].any():
            continue
        f, l = int(first[x]), int(last[x])
        top = f - 1
        while top >= 0 and mask[top, x]:
            top -= 1
        bot = l + 1
        while bot < h and mask[bot, x]:
            bot += 1
        top_c = region[max(top, 0), x]
        bot_c = region[min(bot, h - 1), x]
        span = max(bot - top, 1)
        for y in range(max(f, 0), min(l + 1, h)):
            if not mask[y, x]:
                continue
            t = (y - top) / span
            fill[y, x] = top_c * (1 - t) + bot_c * t
    # weave texture from the donor patch, mirror-tiled
    d0, d1, dc0, dc1 = donor
    patch = img[d0:d1, dc0:dc1].astype(np.float32)
    hf = patch - _box_blur(patch, 6)
    tiles, flip = [], False
    while sum(t.shape[0] for t in tiles) < h:
        tiles.append(hf[::-1] if flip else hf)
        flip = not flip
    hf_big = np.vstack(tiles)[:h, 0:w]
    synth = np.clip(fill + hf_big, 0, 255)
    out = region.copy()
    out[mask] = synth[mask]
    return out


def _pick_donor(L: np.ndarray, bbox, bounds, bg: float):
    """Choose the cleanest texture donor patch around bbox.

    Candidates: strips above/below (same columns) and left/right (same rows),
    clamped to the searchable bounds. Scored by bright-pixel fraction (glyph
    and scene ink are dark against the ground). Returns (r0, r1, c0, c1) with
    width == bbox width (above/below) or >= bbox width (left/right, sliced to
    the exact width by the caller).
    """
    r0, r1, c0, c1 = bbox
    w = c1 - c0
    rmin, rmax, cmin, cmax = bounds
    cands = []
    if r0 - 3 >= rmin + 8:  # above
        d0 = max(rmin, r0 - 3 - 40)
        cands.append(("above", (d0, r0 - 3, c0, c1)))
    if rmax - (r1 + 3) >= 8:  # below
        d1 = min(rmax, r1 + 3 + 40)
        cands.append(("below", (r1 + 3, d1, c0, c1)))
    if c0 - 3 - w >= cmin:  # left
        cands.append(("left", (r0, r1, c0 - 3 - w, c0 - 3)))
    if c1 + 3 + w <= cmax:  # right
        cands.append(("right", (r0, r1, c1 + 3, c1 + 3 + w)))
    best, best_score = None, -1.0
    for name, rect in cands:
        d0, d1, dc0, dc1 = rect
        score = float((np.abs(L[d0:d1, dc0:dc1] - bg) < 25).mean())
        if score > best_score:
            best, best_score = (name, rect), score
    return best


def hf_inpaint(img: np.ndarray, bbox, mask: np.ndarray, donor,
               blur: int = 24) -> np.ndarray:
    """Texture-synthesis repair of masked pixels inside bbox (HxWx3 patch out).

    Low frequency: per-row median of clean pixels (keeps shading). High
    frequency: weave residual donated by a clean patch (same columns where
    possible), mirror-tiled — a flat fill would leave a readable ghost on the
    woven print texture. Larger `blur` = smoother low-frequency base (use a
    big value for large masked areas, e.g. lifted numerals).
    """
    r0, r1, c0, c1 = bbox
    filled = img.copy()
    for y in range(r0, r1):
        m = mask[y - r0]
        if not m.any():
            continue
        good = ~m
        if good.sum() >= 20:
            filled[y, c0:c1][m] = np.median(img[y, c0:c1][good], axis=0)
    d0, d1, dc0, dc1 = donor
    patch = filled[d0:d1, dc0:dc1].astype(np.float32)
    hf = patch - _box_blur(patch, 6)
    tiles, flip = [], False
    while sum(t.shape[0] for t in tiles) < (r1 - r0):
        tiles.append(hf[::-1] if flip else hf)
        flip = not flip
    hf_big = np.vstack(tiles)[: r1 - r0, 0:c1 - c0]
    region = filled[r0:r1, c0:c1].astype(np.float32)
    synth = np.clip(_box_blur(region, blur) + hf_big, 0, 255)
    out = region.copy()
    out[mask] = synth[mask]
    return out


def build_layers(img: np.ndarray, g: dict) -> dict[str, np.ndarray]:
    H, W = img.shape[:2]
    a = g["artwork_rect"]
    hole = g["edge_hole"]
    tb = g.get("text_bbox")
    b = g.get("band")
    nb = g.get("num_bbox")
    L = 0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]

    # artwork: opaque crop on transparent canvas (tucks 8px under frame lines),
    # with the numeral inpainted out (it becomes its own floating layer)
    artwork = np.zeros((H, W, 4), np.uint8)
    artwork[a[0]:a[1], a[2]:a[3], :3] = img[a[0]:a[1], a[2]:a[3]]
    artwork[a[0]:a[1], a[2]:a[3], 3] = 255

    layers: dict[str, np.ndarray] = {}

    if nb:  # majors and pips: numeral as its own floating layer
        number = np.zeros((H, W, 4), np.uint8)
        nr0, nr1, nc0, nc1 = nb
        alpha_n = _glyph_alpha(L[nr0:nr1, nc0:nc1], g["num_bg"],
                               g.get("num_polarity", "dark"))
        number[nr0:nr1, nc0:nc1, :3] = img[nr0:nr1, nc0:nc1]
        number[nr0:nr1, nc0:nc1, 3] = (alpha_n * 255).astype(np.uint8)
        donor_n = g.get("num_donor")
        if donor_n is None:  # legacy layout.json entries
            bounds = (g["inner"][0] + 4, g["separator"][0] - 4,
                      g["inner"][2] + 4, g["inner"][3] - 4)
            _, donor_n = _pick_donor(L, nb, bounds, g["num_bg"])
        # repair mask: any pixel deviating from the ground (glyph core AND
        # anti-aliased fringe) — the alpha ramp alone can miss faint fringe
        if g.get("num_polarity", "dark") == "dark":
            mask_r = L[nr0:nr1, nc0:nc1] < g["num_bg"] - 22
        else:
            mask_r = L[nr0:nr1, nc0:nc1] > g["num_bg"] + 22
        mask_r |= number[nr0:nr1, nc0:nc1, 3] > 0
        artwork[nr0:nr1, nc0:nc1, :3] = vfill_inpaint(
            img, nb, _dilate(mask_r, 12), donor_n)
        layers["number"] = number

    # title: caption glyphs as their own floating layer (band cards only)
    title = None
    r0, r1, c0, c1 = tb if tb else (0, 0, 0, 0)
    if b:
        title = np.zeros((H, W, 4), np.uint8)
        alpha_t = _glyph_alpha(L[r0:r1, c0:c1], g["band_bg"])
        title[r0:r1, c0:c1, :3] = img[r0:r1, c0:c1]
        title[r0:r1, c0:c1, 3] = (alpha_t * 255).astype(np.uint8)

    # edge: full image; artwork window cleared; title text inpainted with
    # band-ground synthesis (the floating text never exposes holes)
    edge = np.dstack([img, np.full((H, W), 255, np.uint8)])
    edge[hole[0]:hole[1], hole[2]:hole[3], 3] = 0
    if b:
        tmask = title[:, :, 3] > 0
        sub0, sub1 = b[2] + 8, b[3] - 8
        donor_b = (b[0] + 5, tb[0] - 4, sub0, sub1)   # clean band strip above text
        edge[r0:r1, c0:c1, :3] = hf_inpaint(
            img, tb, _dilate(tmask[r0:r1, c0:c1], 4), donor_b)
    layers["edge"] = edge
    layers["artwork"] = artwork
    if title is not None:
        layers["title"] = title
    return layers


def band_bg_rgb(img: np.ndarray, g: dict) -> tuple[int, int, int]:
    b = g["band"]
    patch = img[b[0] + 4:b[1] - 4, b[2] + 8:b[3] - 8].reshape(-1, 3)
    return tuple(int(v) for v in np.median(patch, axis=0))


def recomposite(img: np.ndarray, g: dict, layers: dict) -> np.ndarray:
    """artwork <- number <- edge <- title; returns HxWx3 uint8.

    The edge layer is opaque everywhere except the artwork window, and the
    artwork layer is opaque inside that window, so the colour behind them
    never matters — RGB channels only.
    """
    out = None
    for name in ("artwork", "number", "edge", "title"):
        if name not in layers:
            continue
        ly = layers[name].astype(np.float32)
        la = ly[:, :, 3:4] / 255
        base = out if out is not None else np.zeros(ly[:, :, :3].shape, np.float32)
        out = base * (1 - la) + ly[:, :, :3] * la
    return out.astype(np.uint8)


def recomposite_check(img: np.ndarray, g: dict, layers: dict) -> dict:
    """artwork (behind) <- edge <- title; compare with original."""
    diff = np.abs(recomposite(img, g, layers).astype(np.float32)
                  - img.astype(np.float32)).max(axis=2)
    return {"mean": float(diff.mean()), "max": int(diff.max()),
            "gt8_ppm": float((diff > 8).mean() * 1e6)}


# ---- entry ------------------------------------------------------------------

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "analyze":
        cmd_analyze(sys.argv[2:] or ["The Fool"])
    elif cmd == "analyze-all":
        cmd_analyze_all()
    elif cmd == "boxes":
        cmd_boxes(sys.argv[2], sys.argv[3])
    elif cmd == "split":
        cmd_split(sys.argv[2:])
    elif cmd == "split-minors":
        cmd_split_minors()
    elif cmd == "proof":
        cmd_proof(sys.argv[2], sys.argv[3])
    elif cmd == "preview-assets":
        cmd_preview_assets()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
