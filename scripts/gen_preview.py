"""Generate per-card interactive preview pages: processed/preview/.

One self-contained page per card (78 total), each a copy of the single-card
demo (processed/preview.html) wired to that card's layers: hover 2D parallax
(idle = all layers exactly at rest) + rainbow foil + sliders (tilt / artwork
depth / artwork scale / numeral depth / title depth / rainbow intensity /
rainbow travel). Sliders for layers a card doesn't have (number / title) are
omitted automatically. index.html is a plain link list.

Modes:
  python gen_preview.py                 # workspace mode: pages reference the
                                        # full-resolution PNG layers in place
  python gen_preview.py --out DIR --webp
                                        # publishing mode: downscale layers to
                                        # WebP into DIR/assets and reference
                                        # them (self-contained, ~12MB) — used
                                        # for the open-source repo's preview
"""
import argparse
import html
import json
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
PROC = HERE / "processed"
OUT = PROC / "preview"
WEBP_SCALE = 0.25
WEBP_Q = 80


def collect():
    """Return [(section, html_path, label, layer_dir_rel, has_number, has_title)]."""
    cards = []
    rep = json.loads((PROC / "major-arcana/layout.json").read_text(encoding="utf-8"))
    for v in sorted((v for v in rep.values() if "slug" in v), key=lambda v: v["number"]):
        d = f"major-arcana/{v['number']:02d}-{v['slug']}"
        cards.append(("大阿卡纳", f"major/{v['number']:02d}-{v['slug']}.html",
                      f"{v['number']:02d} · {v['slug'].replace('-', ' ').title()}",
                      d))
    rep2 = json.loads((PROC / "minor-arcana/layout.json").read_text(encoding="utf-8"))
    for suit, slabel in (("wands", "权杖 Wands"), ("cups", "圣杯 Cups"),
                         ("swords", "宝剑 Swords"), ("pentacles", "星币 Pentacles")):
        for v in sorted((v for v in rep2.values() if v.get("suit") == suit),
                        key=lambda v: v["rank_number"]):
            base = [k for k, vv in rep2.items() if vv is v][0]
            d = f"minor-arcana/{suit}/{v['rank_number']:02d}-{base.lower().replace(' ', '-')}"
            label = f"{v['rank_number']:02d} · {base}"
            cards.append((f"小阿卡纳 · {slabel}", f"minor/{suit}/{v['rank_number']:02d}-{base.lower().replace(' ', '-')}.html", label, d))
    return cards


def card_page(label, layer_url_prefix, has):
    """Render one per-card page. `has` = dict of present layers."""
    r_num = """
    <label><span>序号视差幅度 <output id="o-num">16px</output></span>
      <input type="range" id="r-num" min="0" max="60" step="1" value="16"></label>""" if has.get("number") else ""
    r_title = """
    <label><span>标题视差幅度 <output id="o-title">22px</output></span>
      <input type="range" id="r-title" min="0" max="60" step="1" value="22"></label>""" if has.get("title") else ""
    js_num = """
  bind('r-num', 'o-num', v => v + 'px', v => { numAmp = v; });""" if has.get("number") else ""
    js_title = """
  bind('r-title', 'o-title', v => v + 'px', v => { titleAmp = v; });""" if has.get("title") else ""
    layers_html = f'''      <img class="artwork" src="{layer_url_prefix}/artwork.png" alt="">
      <img class="edge" src="{layer_url_prefix}/edge.png" alt="">
      <div class="foil"></div>'''
    if has.get("number"):
        layers_html += f'\n      <img class="number" src="{layer_url_prefix}/number.png" alt="">'
    if has.get("title"):
        layers_html += f'\n      <img class="title" src="{layer_url_prefix}/title.png" alt="">'
    js_layers = ""
    if has.get("number"):
        js_layers += """
      card.style.setProperty('--nx', (nx * numAmp).toFixed(1) + 'px');
      card.style.setProperty('--ny', (ny * numAmp).toFixed(1) + 'px');"""
    if has.get("title"):
        js_layers += """
      card.style.setProperty('--tx', (nx * titleAmp).toFixed(1) + 'px');
      card.style.setProperty('--ty', (ny * titleAmp).toFixed(1) + 'px');"""
    js_leave = ""
    for k in ("nx", "ny", "tx", "ty"):
        if (k in ("nx", "ny") and has.get("number")) or (k in ("tx", "ty") and has.get("title")):
            js_leave += f"\n    card.style.setProperty('--{k}', '0px');"
    return PAGE.replace("{{TITLE}}", html.escape(label)) \
               .replace("{{LAYERS}}", layers_html) \
               .replace("{{R_NUM}}", r_num).replace("{{R_TITLE}}", r_title) \
               .replace("{{JS_NUM}}", js_num).replace("{{JS_TITLE}}", js_title) \
               .replace("{{JS_LAYERS}}", js_layers).replace("{{JS_LEAVE}}", js_leave)


PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RWS 拆层预览 — {{TITLE}}</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; min-height:100vh; display:flex; flex-direction:column; align-items:center;
         gap:24px; background:#191713; color:#e8e2d6; font:14px/1.7 system-ui,sans-serif; padding:30px; }
  h1 { font-size:16px; font-weight:600; margin:0; letter-spacing:.04em; }
  p.hint { margin:0; color:#a99e8a; font-size:13px; text-align:center; }
  p.back { margin:0; font-size:13px; }
  p.back a { color:#c9b98a; }
  .stage { perspective: 1100px; position:relative; }
  .card { position:relative; width:min(420px, 80vw); aspect-ratio:2100/3600;
          transform-style:preserve-3d; touch-action:none; }
  .card.live img { will-change: transform; }
  .card img { position:absolute; inset:0; width:100%; height:100%;
              -webkit-user-drag:none; user-select:none; pointer-events:none; }
  /* 视差 = 2D 平移（幅度由滑杆定）：闲置时偏移恒为 0，序号/标题永远精确归位，
     改深度只改动幅不改位置。牌面向后 = 与指针反向；序号/标题浮层 = 同向。 */
  .card .artwork { transform: translate(var(--ax, 0px), var(--ay, 0px)) scale(var(--art-scale, 1.06));
                   transform-origin: 50.1% 46.5%; }
  .card .number  { transform: translate(var(--nx, 0px), var(--ny, 0px)); }
  .card .title   { transform: translate(var(--tx, 0px), var(--ty, 0px)); }
  /* rainbow 箔面：卡内单元素，color-dodge；渐变以 background-size 400% 铺装、
     background-position 随指针扫动（pokemon-cards-css 原版模式，背景天然裁切于卡面）。
     色标取低明度（原版靠 filter brightness 压制，本页按 GPU 红线弃 filter 改色标补偿）。 */
  .card .foil { position:absolute; inset:0; pointer-events:none;
                mix-blend-mode: color-dodge; opacity: var(--rainbow, .5);
                background-image: linear-gradient(-30deg,
      hsl(0,57%,30%), hsl(40,53%,32%), hsl(90,60%,30%), hsl(180,60%,30%),
      hsl(180,60%,30%), hsl(210,57%,32%), hsl(280,55%,26%),
      hsl(0,57%,30%), hsl(40,53%,32%), hsl(90,60%,30%), hsl(180,60%,30%),
      hsl(180,60%,30%), hsl(210,57%,32%), hsl(280,55%,26%),
      hsl(0,57%,30%), hsl(40,53%,32%), hsl(90,60%,30%), hsl(180,60%,30%),
      hsl(180,60%,30%), hsl(210,57%,32%), hsl(280,55%,26%),
      hsl(0,57%,30%));
                background-size: 400% 400%;
                background-position: var(--bx, 50%) var(--by, 50%); }
  .card.live .foil { will-change: background-position; }
  .panel { display:flex; gap:20px 26px; flex-wrap:wrap; justify-content:center; max-width:760px; }
  label { display:flex; flex-direction:column; gap:2px; width:220px; font-size:13px; }
  label span { display:flex; justify-content:space-between; }
  output { color:#c9b98a; font-variant-numeric:tabular-nums; }
  input[type=range] { accent-color:#c9b98a; }
</style>
</head>
<body>
  <h1>RWS 拆层预览 · {{TITLE}}</h1>
  <p class="hint">悬停移动指针：卡片倾斜，牌面向后、序号/标题浮层同向视差，rainbow 随指针扫动。<br>闲置时所有层精确归位；深度滑杆只改视差幅度，不改变闲置位置。</p>
  <p class="back"><a href="../index.html">← 返回牌目录</a></p>
  <div class="stage">
    <div class="card" id="card">
{{LAYERS}}
    </div>
  </div>
  <div class="panel">
    <label><span>倾斜幅度 <output id="o-tilt">16°</output></span>
      <input type="range" id="r-tilt" min="0" max="30" step="1" value="16"></label>
    <label><span>牌面视差幅度 <output id="o-art">14px</output></span>
      <input type="range" id="r-art" min="0" max="40" step="1" value="14"></label>
    <label><span>牌面放大 <output id="o-scale">×1.06</output></span>
      <input type="range" id="r-scale" min="100" max="108" step="0.5" value="106"></label>{{R_NUM}}{{R_TITLE}}
    <label><span>rainbow 强度 <output id="o-rain">50%</output></span>
      <input type="range" id="r-rain" min="0" max="100" step="1" value="50"></label>
    <label><span>rainbow 扫幅 <output id="o-travel">100%</output></span>
      <input type="range" id="r-travel" min="0" max="200" step="5" value="100"></label>
  </div>
<script>
  const card = document.getElementById('card');
  const stage = card.parentElement;
  let rect = null, raf = 0;
  let tiltMax = 16, artAmp = 14, numAmp = 16, titleAmp = 22, travel = 1;

  stage.addEventListener('pointerenter', () => {
    rect = stage.getBoundingClientRect();
    card.classList.add('live');
    card.style.transition = 'transform 80ms ease-out';        // 进场短过渡
    setTimeout(() => { card.style.transition = ''; }, 90);
  });
  stage.addEventListener('pointermove', (e) => {              // move 期间免过渡 1:1 跟手
    if (!rect) rect = stage.getBoundingClientRect();
    const nx = (e.clientX - rect.left) / rect.width * 2 - 1;
    const ny = (e.clientY - rect.top) / rect.height * 2 - 1;
    if (!raf) raf = requestAnimationFrame(() => {
      raf = 0;
      card.style.transform =
        `rotateX(${(-ny * tiltMax).toFixed(2)}deg) rotateY(${(nx * tiltMax).toFixed(2)}deg)`;
      card.style.setProperty('--ax', (-nx * artAmp).toFixed(1) + 'px');   // 牌面反向 = 后退
      card.style.setProperty('--ay', (-ny * artAmp).toFixed(1) + 'px');{{JS_LAYERS}}
      card.style.setProperty('--bx', (50 + nx * 25 * travel).toFixed(1) + '%');
      card.style.setProperty('--by', (50 + ny * 32 * travel).toFixed(1) + '%');
    });
  }, { passive: true });
  stage.addEventListener('pointerleave', () => {              // 离开慢弹回正：全部归零 = 精确归位
    rect = null;
    card.classList.remove('live');
    card.style.transition = 'transform .32s cubic-bezier(.2,.65,.3,1.12)';
    card.style.transform = 'rotateX(0deg) rotateY(0deg)';
    card.style.setProperty('--ax', '0px');
    card.style.setProperty('--ay', '0px');{{JS_LEAVE}}
    card.style.setProperty('--bx', '50%');
    card.style.setProperty('--by', '50%');
    setTimeout(() => { card.style.transition = ''; }, 340);
  });

  const bind = (rid, oid, fmt, fn) => {
    const r = document.getElementById(rid), o = document.getElementById(oid);
    const apply = () => { fn(+r.value); o.textContent = fmt(+r.value); };
    r.addEventListener('input', apply);
    apply();
  };
  bind('r-tilt', 'o-tilt', v => v + '°', v => { tiltMax = v; });
  bind('r-art', 'o-art', v => v + 'px', v => { artAmp = v; });
  bind('r-scale', 'o-scale', v => '×' + (v / 100).toFixed(2),
       v => card.style.setProperty('--art-scale', v / 100));{{JS_NUM}}{{JS_TITLE}}
  bind('r-rain', 'o-rain', v => v + '%', v => card.style.setProperty('--rainbow', v / 100));
  bind('r-travel', 'o-travel', v => v + '%', v => { travel = v / 100; });
</script>
</body>
</html>
"""

INDEX = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RWS 塔罗牌拆层预览 — 78 张单卡页目录</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; padding:28px; background:#191713; color:#e8e2d6;
         font:14px/1.8 system-ui,sans-serif; }
  h1 { font-size:17px; margin:0 0 6px; }
  p { margin:0 0 14px; color:#a99e8a; font-size:13px; }
  h2 { font-size:14px; margin:22px 0 8px; color:#c9b98a; letter-spacing:.05em; }
  .links { display:grid; grid-template-columns:repeat(auto-fill, minmax(210px, 1fr)); gap:4px 18px; }
  a { color:#e8e2d6; text-decoration:none; }
  a:hover { color:#c9b98a; }
</style>
</head>
<body>
  <h1>RWS 塔罗牌拆层预览 · 单卡页目录</h1>
  <p>每张牌一个交互页：悬停视差（闲置精确归位）+ rainbow + 7 滑杆调参；图片为全分辨率分层 PNG。</p>
{{BODY}}
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT,
                    help="output dir (default: processed/preview)")
    ap.add_argument("--webp", action="store_true",
                    help="copy layers as downscaled WebP into OUT/assets and "
                         "reference them (self-contained publishing mode)")
    args = ap.parse_args()
    out = args.out
    cards = collect()
    sections = []
    section = None
    n_conv = 0
    for sec, page_rel, label, layer_dir in cards:
        has = {ly: (PROC / layer_dir / f"{ly}.png").exists()
               for ly in ("artwork", "edge", "number", "title")}
        if not (has["artwork"] and has["edge"]):
            print("SKIP (missing base layers):", layer_dir)
            continue
        if args.webp:
            prefix = "assets/" + layer_dir  # mirrored tree under assets/
            for ly in ("artwork", "edge", "number", "title"):
                s = PROC / layer_dir / f"{ly}.png"
                d = out / "assets" / layer_dir / f"{ly}.webp"
                if s.exists():
                    if not d.exists() or d.stat().st_mtime < s.stat().st_mtime:
                        im = Image.open(s)
                        im = im.resize((round(im.size[0] * WEBP_SCALE),
                                        round(im.size[1] * WEBP_SCALE)), Image.LANCZOS)
                        d.parent.mkdir(parents=True, exist_ok=True)
                        im.save(d, "WEBP", quality=WEBP_Q, method=4)
                        n_conv += 1
        else:
            prefix = "../" * (page_rel.count("/") + 1) + layer_dir
        page_path = out / page_rel
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(card_page(label, prefix, has), encoding="utf-8")
        if sec != section:
            sections.append((sec, []))
            section = sec
        sections[-1][1].append((page_rel, label))
    links = []
    for sec, items in sections:
        links.append(f"<h2>{html.escape(sec)}</h2>")
        links.append('<div class="links">')
        for page_rel, label in items:
            links.append(f'<a href="{html.escape(page_rel)}">{html.escape(label)}</a>')
        links.append("</div>")
    (out / "index.html").write_text(
        INDEX.replace("{{BODY}}", "\n".join(links)), encoding="utf-8")
    print(f"preview: {len(sections)} sections, {n_conv} webp converted, "
          f"per-card pages -> {out/'index.html'}")


if __name__ == "__main__":
    main()
