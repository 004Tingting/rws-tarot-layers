"use client";

import { useEffect, useRef, useState } from "react";

/* ---------- 可调参数（与 preview.html 默认值一致） ---------- */

export type TarotCardTuning = {
  /** 倾斜幅度（deg），默认 16 */
  tilt?: number;
  /** 牌面视差幅度（px，反向），默认 14 */
  art?: number;
  /** 序号浮层视差（px，同向），默认 16 */
  num?: number;
  /** 标题浮层视差（px，同向），默认 22 */
  title?: number;
  /** rainbow 扫幅系数，默认 1 */
  travel?: number;
  /** rainbow 强度 0–1，默认 0.5 */
  rainbow?: number;
  /** 牌面放大倍数（视差时避免露边），默认 1.06 */
  artScale?: number;
};

const DEFAULTS: Required<TarotCardTuning> = {
  tilt: 16,
  art: 14,
  num: 16,
  title: 22,
  travel: 1,
  rainbow: 0.5,
  artScale: 1.06,
};

export type TarotCardProps = {
  /** 牌 id：`major-0`–`major-21` / `wands-1`–`wands-14` / `cups-*` / `swords-*` / `pentacles-*` */
  cardId: string;
  /** 素材根路径，默认 `/tarot`。指向 `assets/` 的部署位置 */
  basePath?: string;
  /** 额外 class（作用于最外层 stage） */
  className?: string;
  /** 无障碍标签；不传则视为纯装饰（aria-hidden） */
  label?: string;
  tuning?: TarotCardTuning;
};

/**
 * RWS 塔罗 3D 闪卡（React）。
 *
 * 分层：artwork / edge / number / title 四层叠加 + rainbow 箔面，
 * 指针进入 → 倾斜 + 牌面反向视差 + 浮层同向视差 + 箔面扫动；离开弹性回正、所有层精确归位。
 *
 * 加载顺序（关键设计）：
 *   ① 先显示**整体牌面** `thumb.webp`（240px 拍平图 ≈29KB，一张就到齐）；
 *   ② artwork + edge 预加载完成 → 才切到分层视图，此时才挂 rainbow 箔面；
 *   ③ 任一必需层加载失败（网络问题）→ 保持整体牌面，**不显示 rainbow**
 *      （半套层 + 彩虹叠在破图上很难看）。
 *
 * 层缺失是正常的（按印版事实）：数字牌 2–10 无 title 层（牌面无牌名带），
 * 5 张缺 number 层（The Moon / The Sun / Four of Cups / Three of Pentacles /
 * Five of Pentacles）。缺失层自动不渲染。
 *
 * `prefers-reduced-motion: reduce` 时不绑定指针事件，仅静态展示。
 */
export function TarotCard({
  cardId,
  basePath = "/tarot",
  className = "",
  label,
  tuning,
}: TarotCardProps) {
  const t = { ...DEFAULTS, ...tuning };
  const base = `${basePath}/${cardId}`;

  const stageRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const rectRef = useRef<DOMRect | null>(null);
  const rafRef = useRef(0);

  const [layersReady, setLayersReady] = useState(false);
  const [hasNumber, setHasNumber] = useState(true);
  const [hasTitle, setHasTitle] = useState(true);

  /* 预加载 artwork + edge；任一失败 → 不切分层 */
  useEffect(() => {
    setLayersReady(false);
    let alive = true;
    const preload = (src: string) =>
      new Promise<boolean>((resolve) => {
        const img = new Image();
        img.onload = () => resolve(true);
        img.onerror = () => resolve(false);
        img.src = src;
      });

    Promise.all([preload(`${base}/artwork.webp`), preload(`${base}/edge.webp`)]).then(
      ([artOk, edgeOk]) => {
        if (alive && artOk && edgeOk) setLayersReady(true);
      },
    );
    return () => {
      alive = false;
    };
  }, [base]);

  /* 指针交互：倾斜 + 视差 + 箔面扫动 */
  useEffect(() => {
    const stage = stageRef.current;
    const card = cardRef.current;
    if (!stage || !card) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let settleTimer = 0;

    const onEnter = () => {
      rectRef.current = stage.getBoundingClientRect();
      card.classList.add("rws-live");
      card.style.transition = "transform 80ms ease-out";
      window.setTimeout(() => {
        card.style.transition = "";
      }, 90);
    };

    const onMove = (e: PointerEvent) => {
      const rect = rectRef.current ?? stage.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const nx = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const ny = ((e.clientY - rect.top) / rect.height) * 2 - 1;
      if (rafRef.current) return;
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = 0;
        card.style.transform = `rotateX(${(-ny * t.tilt).toFixed(2)}deg) rotateY(${(nx * t.tilt).toFixed(2)}deg)`;
        card.style.setProperty("--rws-ax", `${(-nx * t.art).toFixed(1)}px`);
        card.style.setProperty("--rws-ay", `${(-ny * t.art).toFixed(1)}px`);
        card.style.setProperty("--rws-nx", `${(nx * t.num).toFixed(1)}px`);
        card.style.setProperty("--rws-ny", `${(ny * t.num).toFixed(1)}px`);
        card.style.setProperty("--rws-tx", `${(nx * t.title).toFixed(1)}px`);
        card.style.setProperty("--rws-ty", `${(ny * t.title).toFixed(1)}px`);
        card.style.setProperty("--rws-bx", `${(50 + nx * 25 * t.travel).toFixed(1)}%`);
        card.style.setProperty("--rws-by", `${(50 + ny * 32 * t.travel).toFixed(1)}%`);
      });
    };

    const onLeave = () => {
      rectRef.current = null;
      card.classList.remove("rws-live");
      card.style.transition = "transform .32s cubic-bezier(.2,.65,.3,1.12)";
      card.style.transform = "rotateX(0deg) rotateY(0deg)";
      for (const k of ["ax", "ay", "nx", "ny", "tx", "ty"]) {
        card.style.setProperty(`--rws-${k}`, "0px");
      }
      card.style.setProperty("--rws-bx", "50%");
      card.style.setProperty("--rws-by", "50%");
      window.clearTimeout(settleTimer);
      settleTimer = window.setTimeout(() => {
        card.style.transition = "";
      }, 340);
    };

    stage.addEventListener("pointerenter", onEnter);
    stage.addEventListener("pointermove", onMove, { passive: true });
    stage.addEventListener("pointerleave", onLeave);
    return () => {
      stage.removeEventListener("pointerenter", onEnter);
      stage.removeEventListener("pointermove", onMove);
      stage.removeEventListener("pointerleave", onLeave);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      window.clearTimeout(settleTimer);
    };
  }, [t.tilt, t.art, t.num, t.title, t.travel]);

  const layerStyle: React.CSSProperties = { position: "absolute", inset: 0, width: "100%", height: "100%" };

  return (
    <div
      ref={stageRef}
      className={`rws-stage ${className}`}
      style={{ perspective: 1100, position: "relative", width: "100%", pointerEvents: "auto" }}
      {...(label ? { role: "img", "aria-label": label } : { "aria-hidden": true })}
    >
      <div
        ref={cardRef}
        className="rws-card"
        style={{
          position: "relative",
          width: "100%",
          aspectRatio: "2100 / 3600",
          transformStyle: "preserve-3d",
          touchAction: "none",
        }}
      >
        {/* ① 整体牌面：先出这张，分层就绪后隐藏 */}
        <img
          className="rws-thumb"
          src={`${base}/thumb.webp`}
          alt=""
          draggable={false}
          hidden={layersReady}
          style={{ ...layerStyle, objectFit: "cover", pointerEvents: "none", userSelect: "none" }}
        />

        {/* ② 分层视图：artwork + edge 就绪后才渲染，rainbow 同时才出现 */}
        {layersReady && (
          <>
            <img
              className="rws-artwork"
              src={`${base}/artwork.webp`}
              alt=""
              draggable={false}
              style={{
                ...layerStyle,
                pointerEvents: "none",
                userSelect: "none",
                transform:
                  "translate(var(--rws-ax, 0px), var(--rws-ay, 0px)) scale(var(--rws-art-scale, 1.06))",
                transformOrigin: "50.1% 46.5%",
              }}
            />
            <img
              className="rws-edge"
              src={`${base}/edge.webp`}
              alt=""
              draggable={false}
              style={{ ...layerStyle, pointerEvents: "none", userSelect: "none" }}
            />
            {/* rainbow 箔面：只在分层就绪后挂载 */}
            <div
              className="rws-rainbow"
              style={{
                ...layerStyle,
                pointerEvents: "none",
                mixBlendMode: "color-dodge",
                opacity: t.rainbow,
                backgroundImage: RAINBOW_GRADIENT,
                backgroundSize: "400% 400%",
                backgroundPosition: "var(--rws-bx, 50%) var(--rws-by, 50%)",
              }}
            />
            {hasNumber && (
              <img
                className="rws-number"
                src={`${base}/number.webp`}
                alt=""
                draggable={false}
                onError={() => setHasNumber(false)}
                style={{
                  ...layerStyle,
                  pointerEvents: "none",
                  userSelect: "none",
                  transform: "translate(var(--rws-nx, 0px), var(--rws-ny, 0px))",
                }}
              />
            )}
            {hasTitle && (
              <img
                className="rws-title"
                src={`${base}/title.webp`}
                alt=""
                draggable={false}
                onError={() => setHasTitle(false)}
                style={{
                  ...layerStyle,
                  pointerEvents: "none",
                  userSelect: "none",
                  transform: "translate(var(--rws-tx, 0px), var(--rws-ty, 0px))",
                }}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}

/**
 * rainbow 箔面渐变（-30° 七色 ×3 循环）。
 * 色标取低明度：原版 pokemon-cards-css 靠 filter brightness 压制，
 * 这里按 GPU 红线弃用 filter、改色标补偿。
 */
const RAINBOW_GRADIENT =
  "linear-gradient(-30deg," +
  "hsl(0,57%,30%),hsl(40,53%,32%),hsl(90,60%,30%),hsl(180,60%,30%)," +
  "hsl(180,60%,30%),hsl(210,57%,32%),hsl(280,55%,26%)," +
  "hsl(0,57%,30%),hsl(40,53%,32%),hsl(90,60%,30%),hsl(180,60%,30%)," +
  "hsl(180,60%,30%),hsl(210,57%,32%),hsl(280,55%,26%)," +
  "hsl(0,57%,30%),hsl(40,53%,32%),hsl(90,60%,30%),hsl(180,60%,30%)," +
  "hsl(180,60%,30%),hsl(210,57%,32%),hsl(280,55%,26%)," +
  "hsl(0,57%,30%))";

export default TarotCard;
