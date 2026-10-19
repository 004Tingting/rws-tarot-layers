"""Download the Rider-Waite-Smith tarot deck (Geldard scan set) from Wikimedia Commons.

Usage:
  python download_from_commons.py manifest   # enumerate files, write manifest.json, print size stats
  python download_from_commons.py download   # download all files listed in manifest.json (resumable: skips complete files)
  python download_from_commons.py verify     # check PNG signature + IHDR dims vs manifest, report mismatches

Naming pattern on Commons: "<Card name> (Rider-Waite Smith tarot deck).png"
The deck is public domain (published 1909). Be polite: proper User-Agent, small delay.
"""
import json
import re
import subprocess
import sys
import time
import struct
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = "WidgetsWorkspace-assets/1.0 (local development; one-off bulk fetch of PD images)"
SUFFIX = "(Rider-Waite Smith tarot deck)"
HERE = Path(__file__).resolve().parent
CARDS_DIR = HERE / "cards"
MANIFEST = HERE / "manifest.json"


def api(params: dict) -> dict:
    params = dict(params, format="json")
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def enumerate_files() -> list[str]:
    """All Commons file pages whose title ends with the Geldard naming suffix."""
    titles = []
    cont = {}
    while True:
        data = api({
            "action": "query", "list": "search",
            "srsearch": 'intitle:"Rider-Waite Smith tarot deck"', "srnamespace": "6",
            "srlimit": "500", **cont,
        })
        hits = data.get("query", {}).get("search", [])
        titles += [h["title"] for h in hits]
        cont = data.get("continue")
        if not cont:
            break
        time.sleep(0.3)
    pat = re.compile(r"^File:(.+) " + re.escape(SUFFIX + ".png") + r"$")
    names = sorted({m.group(1) for t in titles if (m := pat.match(t))})
    return names


def imageinfo(names: list[str]) -> dict:
    """Batched imageinfo: name -> {url, size, width, height, descriptionurl}."""
    info = {}
    for i in range(0, len(names), 50):
        batch = names[i:i + 50]
        data = api({
            "action": "query", "prop": "imageinfo",
            "iiprop": "url|size",
            "titles": "|".join(f"File:{n} {SUFFIX}.png" for n in batch),
        })
        for page in data["query"]["pages"].values():
            if "imageinfo" not in page:
                print(f"  !! no imageinfo: {page.get('title')}")
                continue
            n = re.sub(r"^File:|\.\w+$", "", page["title"])
            n = re.sub(" " + re.escape(SUFFIX) + r"$", "", n)
            ii = page["imageinfo"][0]
            info[n] = {"url": ii["url"].split("?")[0], "size": ii["size"],
                       "width": ii["width"], "height": ii["height"]}
        time.sleep(0.3)
    return info


def fetch(url: str, dest: Path, expected: int) -> str:
    if dest.exists() and dest.stat().st_size == expected:
        return "skip"
    part = dest.with_suffix(dest.suffix + ".part")
    r = None
    for wait in (0, 15):  # one quick retry; persistent 429 => abort whole run
        if wait:
            time.sleep(wait)
        r = subprocess.run(["curl", "-sS", "--fail", "--max-time", "300",
                            "-A", UA, "-o", str(part), url])
        if r.returncode == 0 and part.exists() and part.stat().st_size == expected:
            part.replace(dest)
            return "ok"
    if r.returncode == 22:  # HTTP >=400 from curl --fail; 429 hard block most likely
        return "HARD429"
    return f"FAIL curl rc={r.returncode}"


def png_dims(path: Path):
    with open(path, "rb") as f:
        sig = f.read(8)
        if sig != b"\x89PNG\r\n\x1a\n":
            return None
        f.read(4)
        if f.read(4) != b"IHDR":
            return None
        w, h = struct.unpack(">II", f.read(8))
        return w, h


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "manifest":
        names = enumerate_files()
        print(f"matched {len(names)} file titles")
        info = imageinfo(names)
        manifest = [{"name": n, **info[n]} for n in names if n in info]
        MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        total = sum(e["size"] for e in manifest)
        print(f"manifest: {len(manifest)} files, total {total/1e6:.1f} MB")
        for e in manifest:
            print(f"  {e['name']}: {e['width']}x{e['height']} {e['size']/1e6:.1f} MB")
    elif cmd == "download":
        entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
        CARDS_DIR.mkdir(exist_ok=True)
        bad = {}
        block_wait = 0  # total seconds spent waiting out hard 429 blocks
        for i, e in enumerate(entries, 1):
            dest = CARDS_DIR / f"{e['name']} {SUFFIX}.png"
            while True:
                res = fetch(e["url"], dest, e["size"])
                if res in ("ok", "skip") or not res == "HARD429":
                    break
                block_wait += 600
                if block_wait > 8 * 3600:  # safety cap: ~8h of blocking => give up
                    print(f"giving up after {block_wait}s of blocks", flush=True)
                    bad[e["name"]] = res
                    break
                print(f"  blocked; sleeping 600s (waited {block_wait}s total)",
                      flush=True)
                time.sleep(600)
            print(f"[{i}/{len(entries)}] {res}: {e['name']}", flush=True)
            if res not in ("ok", "skip"):
                bad[e["name"]] = res
                break  # non-429 failure: stop and report
            time.sleep(8)  # politeness gap between bulk fetches
        print(f"\ndone: {len(entries) - len(bad)} ok/skip, {len(bad)} bad")
        for n, r in bad.items():
            print(f"  {r}: {n}")
        sys.exit(1 if bad else 0)
    elif cmd == "verify":
        entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
        problems = []
        for e in entries:
            p = CARDS_DIR / f"{e['name']} {SUFFIX}.png"
            if not p.exists():
                problems.append(f"missing: {p.name}")
                continue
            if p.stat().st_size != e["size"]:
                problems.append(f"size {p.stat().st_size}!={e['size']}: {p.name}")
            if png_dims(p) != (e["width"], e["height"]):
                problems.append(f"dims {png_dims(p)}!=({e['width']},{e['height']}): {p.name}")
        print(f"verify: {len(entries)} expected, {len(problems)} problems")
        for p in problems:
            print("  " + p)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
