# RWS Tarot Card Layers — 韦特塔罗牌 3D 卡面分层

将 1909 年 Rider-Waite-Smith（韦特）塔罗牌的 **78 张公版牌面** 自动拆解为
Web 分层素材（牌面 artwork / 卡边缘 edge / 牌名 title / 罗马数字 number），
配套**逐牌交互预览页**（悬停视差 + rainbow 箔面 + 调参滑杆）与一条从
Commons 下载原图到生成全部分层的完整可复现管线。

> ⚠️ **拆解瑕疵声明（请先阅读）**
>
> 拆解由全自动图像检测完成（无人工标注），**已知存在以下瑕疵**：
>
> 1. **序号浮层缺失 5 张**：`The Moon` / `The Sun`（顶部罗马数字与画面光芒/云气
>    在墨迹上连通，自动分离不可行）与 `Four of Cups` / `Three of Pentacles` /
>    `Five of Pentacles`（检测未命中）。这些牌的罗马数字保留在 artwork 层内，
>    按"无序号浮层"使用。
> 2. **artwork 去数字处有修补痕迹**：数字被提取后，原位置的底面由算法合成
>    （逐列垂直插值 + 织纹平铺）。平色底（黄纸面、黑底）基本无痕；**有结构的底
>    （蓝天白云、光芒、图案）会留下竖向条纹或轻微色块**，近看可辨。
> 3. **序号层边缘可能带少量场景墨迹**：个别卡（如 Wheel of Fortune 的云缘、
>    Judgement 的发丝、Ten of Swords 的红色天空边缘）在连通域合并时可能带入
>    与数字相邻的少量非数字笔画。
> 4. **title 层仅覆盖有牌名带的 45 张**：本印版数字牌（2–10）牌面上没有牌名
>    文字（这是印版事实，非缺陷）；A 牌与宫廷牌有带。已加"居中且宽 ≥45% 带宽"
>    校验防止把作者签名误提为牌名，但不排除边缘案例。
> 5. **未做**：牌背（card back）拆层；分层质量的全量人工复核。
>
> 逐卡检测参数与降级原因记录在各 `layout.json`（`number_layer` 字段）；
> 修复思路见文末「改进方向」。使用前请按自己的质量标准抽查。

---

## 特性总览

- **78 张分层**：每张牌一个目录（`major-arcana/NN-slug/`、
  `minor-arcana/<suit>/NN-rank/`），层为 2100×3600 RGBA PNG，按
  `position:absolute; inset:0` 直接叠放即可做分层视差。
- **层构成自动适配印版事实**：大阿卡纳 20/22 含序号浮层；数字牌（2–10）
  33/36 含序号浮层；A 牌与宫廷牌（16 张）为 edge+artwork+title。
  每卡的层构成记录在 `layout.json`。
- **逐牌交互预览页 ×78**（`preview/`）：悬停 = 牌面向后、序号/标题浮层同向
  视差、rainbow 箔面随指针扫动；**闲置时全部层精确归位**（视差用 2D 平移实现，
  幅度可调）；滑杆按该卡层构成自动增减。
- **rainbow 箔面**：按 [pokemon-cards-css](https://github.com/simeydotme/pokemon-cards-css)
  的 rainbow 配方复刻（-30° 七色渐变 ×3 循环 + color-dodge），仅借鉴思路、
  代码自写，按 GPU 红线弃用 filter、以低明度色标补偿。
- **全管线可复现**：从 Wikimedia Commons 下载原图 → 版式检测 → 拆层 →
  重组校验（叠回 vs 原图逐像素 diff）→ 预览生成，全部脚本化。

## 快速开始

```bash
# 1) 浏览预览（自包含，直接双击 preview/index.html 或起服务）
cd preview && python -m http.server 8651   # 访问 http://localhost:8651

# 2) 下载原牌面（公版，~1 GB）并校验
python scripts/download_from_commons.py manifest
python scripts/download_from_commons.py download
python scripts/download_from_commons.py verify

# 3) 生成全分辨率分层（~1.8 GB，写入 processed/）
python scripts/process_cards.py split
python scripts/process_cards.py split-minors

# 4) 重新生成预览页（全分辨率引用 / webp 自包含两种模式）
python scripts/gen_preview.py --out preview_full    # 引用 processed/ 的 PNG
python scripts/gen_preview.py --out preview --webp  # webp 自包含（本仓库采用）
```

> 本仓库 `preview/` 已内置 webp 缩图预览，无需下载原牌面即可浏览；
> 全分辨率分层（~1.8 GB）请到 **Releases** 下载，或用步骤 2–3 自行生成。

## 调参方式

| 想改什么 | 改哪里 |
|---|---|
| 预览页视差幅度/放大/rainbow | 每页内置滑杆（倾斜/牌面深度/牌面放大/序号深度/标题深度/rainbow 强度/扫幅）；默认值在各页源码内联 |
| 序号芯片判定 | `process_cards.py` → `_numeral_chip()`（模板行窗、双极性七档阈值、字符合并参数、尺寸/居中约束、覆盖率裁切） |
| 序号提取失败的卡 | `process_cards.py` 加人工 bbox 覆盖表（见 layout.json `number_layer` 标注的卡） |
| 去数字修补质量 | `process_cards.py` → `vfill_inpaint()`（供体区选择 `_pick_donor`、织纹幅值、膨胀半径）；修补掩码膨胀 12px |
| 预览缩图质量 | `gen_preview.py` 顶部 `WEBP_SCALE`（默认 0.25）/`WEBP_Q`（80） |
| 重新打包预览 | `python scripts/gen_preview.py --out preview --webp`（mtime 缓存，仅重转改动的层） |

## 兼容性

- 预览页：近两年 Chrome/Edge/Firefox/Safari（`mix-blend-mode` + 2D transform；
  无 WebGL、无构建、无依赖）。已在 Chromium 实测。
- 分层 PNG：RGBA 2100×3600，任何能显示 PNG 的环境可用；WebP 预览同。
- 注意：预览的 `mix-blend-mode` 层**不要放进 `preserve-3d` 子树**
  （Chromium 会出现合成伪影——本仓库采用卡内 background 方案规避）。

## 已知瑕疵（汇总见顶部声明）与改进方向

- [ ] The Moon / The Sun 序号与光芒连通：可试局部 UV/颜色空间分割
- [ ] 修补痕迹：结构底的竖向条纹（PatchMatch 类纹理合成可解，当前为轻量插值+织纹）
- [ ] 序号层边缘场景墨迹：更紧的覆盖率裁切或人工标注覆盖表
- [ ] 全量人工质检

## 文件结构

```
├── preview/                  # 78 个逐牌交互页 + index.html（webp 自包含）
│   └── assets/               # webp 分层缩图（~12MB）
├── scripts/
│   ├── download_from_commons.py   # 从 Commons 枚举+下载+校验原牌面（串行/断点续传/限流退避）
│   ├── process_cards.py           # 版式检测 + 拆层 + 重组校验（analyze/boxes/split/split-minors/proof）
│   └── gen_preview.py             # 预览页生成（workspace 全分辨率 / --webp 发布两种模式）
├── NOTICE.md                 # 素材来源与许可（牌面为公有领域）
├── LICENSE                   # 代码许可（MIT）
└── CHANGELOG.md
```

## 许可

- **代码**：MIT（见 LICENSE）
- **牌面图与分层产物**：公有领域（RWS 1909 年出版；扫描件取自 Wikimedia
  Commons，来源与页面链接见 NOTICE.md），可任意使用。

## 路线图

- [ ] 序号浮层补齐（人工 bbox 覆盖表 / 更强的分离算法）
- [ ] 牌背拆层
- [ ] 修补算法升级（纹理合成）
- [ ] 英文版 README

---

## License (English summary)

Code: MIT. The card artwork and derived layers are in the **public domain**
(Rider-Waite-Smith deck, published 1909; scans from Wikimedia Commons — see
NOTICE.md). **Known flaws of the automated splitting are documented at the top
of this README** (missing numeral overlays on 5 cards, visible inpainting
traces on structured backgrounds, occasional scene ink in the numeral layers).
