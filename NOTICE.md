# NOTICE — 素材来源与许可

本仓库包含以下第三方素材，使用前请阅读：

## 1. Rider-Waite-Smith 塔罗牌牌面（公有领域）

- **扫描集**：Wikimedia Commons 分类
  [Rider-Waite-Smith tarot deck (Geldard)](https://commons.wikimedia.org/wiki/Category:Rider-Waite-Smith_tarot_deck_(Geldard))
  ——78 张 PNG，2100×3600，命名规律 `<Card name> (Rider-Waite Smith tarot deck).png`
  （注意两张使用 `One of Pentacles` / `One of Swords` 而非 `Ace of`）。
- **牌背**：[Waite–Smith Tarot Roses and Lilies cropped.jpg](https://commons.wikimedia.org/wiki/File:Waite%E2%80%93Smith_Tarot_Roses_and_Lilies_cropped.jpg)
  （1909 年原版牌背"玫瑰与百合"图案扫描，扫自 Saskia Jansen 个人藏品）。
- **许可**：RWS 牌 1909 年出版，已进入**公有领域**（Commons 各文件页标注
  Public domain）。本仓库的分层产物为其派生物，同样处于公有领域；
  无署名义务，出处记录于本文件以备查。

## 2. rainbow 箔面配方（仅借鉴思路，未复制代码）

- 参考 [simeydotme/pokemon-cards-css](https://github.com/simeydotme/pokemon-cards-css)
  （GPL-3.0）的 rainbow 卡面配方（-30° 七色渐变 ×3 循环 + color-dodge）。
  本仓库预览页的箔面为**独立实现**：仅借鉴渐变组织思路与混合模式选型，
  未复制其代码或素材；按本工作区 GPU 红线弃用其 `filter` 与 PNG 纹理，
  以低明度色标补偿。此借鉴不产生 GPL 传染义务（无代码复制），特此致谢。

## 3. 本仓库原创部分

- 版式检测、序号芯片检测（连通域）、拆层与修补算法（`vfill_inpaint`/
  `hf_inpaint`）、重组校验、下载限流处理、预览页生成与交互（`scripts/*.py`
  与 `preview/*.html`）——MIT 许可（见 LICENSE）。
