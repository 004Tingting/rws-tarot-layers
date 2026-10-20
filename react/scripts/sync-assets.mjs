#!/usr/bin/env node
/**
 * 从个人站点的 public/tarot 同步 78 张 Web 素材 → react/assets/
 *
 * 包内自带素材（约 11 MB）是为了「装上就能用」：
 * 使用者不必自己跑拆层管线，也不必下 1.7 GB 全分辨率 PNG。
 *
 * 用法：
 *   node scripts/sync-assets.mjs
 *   node scripts/sync-assets.mjs --src D:/other/public/tarot
 *
 * 素材来源：Rider-Waite-Smith 1909 公版牌面（Wikimedia Commons / Geldard 扫描集），
 * 经 process_cards.py 自动拆层、再缩为 480px 分层 + 240px 拍平缩略图。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PKG = path.resolve(HERE, "..");
const args = process.argv.slice(2);
const argOf = (name, dflt) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : dflt;
};

const SRC = path.resolve(argOf("src", "P:/personal-site/public/tarot"));
const DEST = path.join(PKG, "assets");

const LAYERS = ["artwork", "edge", "number", "title", "thumb"];

if (!fs.existsSync(SRC)) {
  console.error(`✗ 源目录不存在：${SRC}`);
  process.exit(1);
}

const cards = fs
  .readdirSync(SRC)
  .filter((n) => fs.statSync(path.join(SRC, n)).isDirectory());

let copied = 0;
let bytes = 0;
let missing = 0;

for (const cardId of cards) {
  const outDir = path.join(DEST, cardId);
  fs.mkdirSync(outDir, { recursive: true });

  for (const layer of LAYERS) {
    const src = path.join(SRC, cardId, `${layer}.webp`);
    if (!fs.existsSync(src)) {
      if (layer !== "number" && layer !== "title") {
        console.warn(`  ⚠ ${cardId}/${layer}.webp 缺失（必需层）`);
        missing++;
      }
      continue;
    }
    const dst = path.join(outDir, `${layer}.webp`);
    fs.copyFileSync(src, dst);
    copied++;
    bytes += fs.statSync(dst).size;
  }
}

console.log(`✓ 素材已同步 → react/assets/（${cards.length} 张）`);
console.log(`  复制 ${copied} 个文件 · ${(bytes / 1024 / 1024).toFixed(2)} MB`);
if (missing) console.log(`  ⚠ 缺失必需层 ${missing} 个`);
