# rws-tarot-card — React 3D 塔罗闪卡

React 组件版塔罗卡：**78 张 Rider-Waite-Smith 公版牌面**，分层视差 + rainbow 箔面，
指针倾斜跟随、离开弹性回正。素材已内置（480px WebP，约 11 MB），装上即用。

> 本包是 [`rws-tarot-layers`](../) 的**下游产物**：那边负责「从公版扫描件拆出分层」，
> 这边负责「把分层做成一个能直接用的 React 组件」。
> 拆层的已知瑕疵（5 张缺序号浮层、修补痕迹）在上游 README 有完整声明，本包如实继承。

---

## 特性

| 特性 | 说明 |
|---|---|
| 分层视差 | artwork / edge / number / title 四层独立，牌面向后、浮层同向，闲置时精确归位 |
| rainbow 箔面 | `mix-blend-mode: color-dodge`，随指针扫动；色标取低明度（弃用 filter，省 GPU） |
| 指针倾斜 | 默认 16°，`transform` + CSS 变量驱动，rAF 合帧 |
| 渐进加载 | 先出整体牌面（29KB），分层就绪才切换并挂 rainbow |
| 失败降级 | 分层加载失败 → 停在整体牌面，**不显示 rainbow** |
| 缺层自适应 | 层不存在就不渲染（数字牌无牌名带、5 张缺序号） |
| 无障碍 | 传 `label` 则 `role="img"`，不传则 `aria-hidden` |
| 减弱动效 | `prefers-reduced-motion: reduce` 时不绑定指针事件，仅静态展示 |

## 快速开始

```bash
npm i rws-tarot-card          # 或直接复制 src/ + assets/
```

```tsx
import { TarotCard } from "rws-tarot-card";

export default function Demo() {
  return (
    <div style={{ width: 220 }}>
      <TarotCard cardId="major-0" basePath="/tarot" label="愚者" />
    </div>
  );
}
```

把 `assets/` 里的 78 个目录放到 `basePath` 指向的位置（示例为 `public/tarot/`），
结构必须是 `public/tarot/<card-id>/{artwork,edge,number,title,thumb}.webp`。

## 素材

包内 `assets/` 已含 78 张 × 5 层（分层 480px + 拍平缩略图 240px），**11.24 MB / 333 文件**。

```bash
node scripts/sync-assets.mjs                      # 从默认位置重新同步
node scripts/sync-assets.mjs --src D:/other/tarot # 换源
```

| 层 | 尺寸 | 单张 | 用途 |
|---|---|---|---|
| `artwork.webp` | 480×823 | 84–105 KB | 牌面（反向视差 + 放大裁切） |
| `edge.webp` | 480×823 | 6–20 KB | 边框 |
| `number.webp` | 480×823 | 2–3 KB | 序号浮层（同向视差） |
| `title.webp` | 480×823 | 10–17 KB | 牌名浮层（同向视差） |
| `thumb.webp` | 240×411 | 22–29 KB | 整体牌面（首帧 + 降级） |

**为什么 480px**：卡片实际显示 ≤208px，2×DPR 需 416px。再往上 600px 到 159 KB/张、
720px 到 216 KB/张，收益不抵体积。

## 层覆盖（按印版事实，不是缺陷）

| 层 | 覆盖 | 缺谁 |
|---|---|---|
| artwork / edge | 78 / 78 | — |
| number | 54 / 78 | The Moon、The Sun（数字与光芒墨迹连通）+ Four of Cups、Three of Pentacles、Five of Pentacles（检测未命中） |
| title | 45 / 78 | 数字牌 2–10 牌面本就无牌名带 |

缺层时组件不渲染对应 `<img>`，无需手动判断。

## 调参

```tsx
<TarotCard
  cardId="major-0"
  tuning={{
    tilt: 16,        // 倾斜幅度 deg
    art: 14,         // 牌面视差 px（反向）
    num: 16,         // 序号视差 px（同向）
    title: 22,       // 标题视差 px（同向）
    travel: 1,       // rainbow 扫幅系数
    rainbow: 0.5,    // rainbow 强度 0–1
    artScale: 1.06,  // 牌面放大（防视差露边）
  }}
/>
```

| 想改什么 | 改哪里 |
|---|---|
| 默认视差/倾斜/rainbow | `src/TarotCard.tsx` 顶部的 `DEFAULTS` |
| rainbow 配色 | 同文件底部 `RAINBOW_GRADIENT` |
| 素材分辨率 | `scripts/sync-assets.mjs` 配合上游 `gen_preview.py` 的 `WEBP_SCALE` |
| 卡面宽高比 | 组件内 `aspectRatio: "2100 / 3600"`（RWS 原始比例） |

## 本地演示

```bash
cd .demo && npm install
npx vite build --config vite.config.mjs
cd .. && cp -r assets demo-dist/card-assets   # 素材不参与打包，构建后复制
python -m http.server 8671 -d demo-dist       # 打开 http://localhost:8671/demo.html
```

演示页放 8 张卡，覆盖「四层齐全 / 缺 number / 无 title」三种层构成。

### 已验证（headless Chrome + CDP，`node .demo/verify.mjs`）

```
✓ 8 张卡全部渲染
✓ 首帧 thumb 可见、无分层、无 rainbow（3Mbps 限速下抓到中间态）
✓ 稳态切分层 + rainbow
✓ hover 视差生效（--rws-ax 7.0px / rotateX 8deg / rotateY -8deg）
✓ 交互期 live 类
✓ major-18 缺 number 不渲染
✓ cups-3 缺 title 不渲染
```

## 兼容性

- React 18 / 19（`peerDependencies: >=18`）
- 需要 `"use client"`（Next.js App Router 已在文件头标注）
- 浏览器：近两年 Chrome / Edge / Firefox / Safari（`mix-blend-mode` + CSS transform，无 WebGL）
- **不要把 rainbow 层放进 `preserve-3d` 子树**——Chromium 会出合成伪影；
  本组件把箔面做成卡内兄弟层规避

## 已知限制

- 5 张缺序号浮层（见上表），序号留在 artwork 层内
- artwork 去数字处为算法修补，结构底（蓝天、光芒）近看有竖向条纹
- 未做牌背；未做翻面（本组件只负责正面展示）
- 480px 适合网页展示，印刷/大屏请用上游 Release 的全分辨率分层

## 许可

- **代码**：MIT（见 [`../LICENSE`](../LICENSE)）
- **牌面素材**：公有领域（RWS 1909 年出版，Wikimedia Commons 扫描，见 [`../NOTICE.md`](../NOTICE.md)）
