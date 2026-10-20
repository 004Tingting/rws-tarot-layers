import { spawn } from "node:child_process";

/**
 * CDP 探针：验证 rws-tarot-card 的 React 包在真实浏览器里工作。
 *
 * 检查项：
 *   ① 8 张卡都渲染出 stage/card 结构
 *   ② 首帧 thumb 可见、无分层、无 rainbow
 *   ③ 稳态切到分层 + rainbow
 *   ④ hover 后 CSS 变量变化（视差生效）+ transform 非空
 *   ⑤ 缺层卡片（major-18 无 number / cups-3 无 title）不渲染对应 img
 *
 * 用法：node .demo/verify.mjs（先 `npx vite build` 并复制 card-assets）
 */
const PORT = 9228;
const URL = "http://localhost:8671/demo.html";
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const chrome = spawn(CHROME, [
  "--headless=new", "--no-proxy-server",
  `--remote-debugging-port=${PORT}`,
  "--window-size=1400,1000", "about:blank",
], { stdio: "ignore" });

await sleep(2500);
const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
const page = list.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));

let id = 0;
const send = (m, p = {}) => {
  const myId = ++id;
  ws.send(JSON.stringify({ id: myId, method: m, params: p }));
  return new Promise((resolve, reject) => {
    const to = setTimeout(() => reject(new Error(`timeout ${m}`)), 20000);
    const onMsg = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id === myId) {
        clearTimeout(to);
        ws.removeEventListener("message", onMsg);
        resolve(msg.result);
      }
    };
    ws.addEventListener("message", onMsg);
  });
};

await send("Page.enable");
await send("Runtime.enable");
await send("Network.enable");

/* 限速 3Mbps：让 84KB artwork 需要约 250ms，才能抓到「thumb 已出、分层未到」的中间态。
   不限速时本地服务器瞬时返回，中间态根本不存在于采样窗口。 */
await send("Network.emulateNetworkConditions", {
  offline: false,
  latency: 150,
  downloadThroughput: (3 * 1024 * 1024) / 8,
  uploadThroughput: (1 * 1024 * 1024) / 8,
});

await send("Page.navigate", { url: URL });

/* 本地服务器太快，3 秒后必然已就绪——高频采样抓中间态（最多 6 秒） */
const STATE_EARLY = `(() => {
  const s = document.querySelector('.rws-stage');
  if (!s) return null;
  const thumb = s.querySelector('.rws-thumb');
  return {
    thumbHidden: thumb ? thumb.hidden : null,
    thumbComplete: thumb ? (thumb.complete && thumb.naturalWidth > 0) : null,
    hasArtwork: !!s.querySelector('.rws-artwork'),
    rainbow: !!s.querySelector('.rws-rainbow'),
  };
})()`;

const seen = [];
for (let i = 0; i < 60; i++) {
  const r = await send("Runtime.evaluate", { expression: STATE_EARLY, returnByValue: true });
  if (r.result.value) seen.push(r.result.value);
  await sleep(100);
}

const sawIntermediate = seen.some(
  (s) => s.thumbHidden === false && s.hasArtwork === false && s.rainbow === false,
);
console.log(`采样 ${seen.length} 帧，中间态出现: ${sawIntermediate}`);
await sleep(1500);

const STATE = `(() => {
  const stages = [...document.querySelectorAll('.rws-stage')];
  return {
    count: stages.length,
    first: stages[0] ? {
      thumbHidden: stages[0].querySelector('.rws-thumb')?.hidden,
      hasArtwork: !!stages[0].querySelector('.rws-artwork'),
      rainbow: !!stages[0].querySelector('.rws-rainbow'),
    } : null,
    /* 缺层检查 */
    major18Number: !!document.querySelector('.rws-stage:nth-child(2) .rws-number'),
    cups3Title: !!document.querySelector('.rws-stage:nth-child(5) .rws-title'),
  };
})()`;

const early = { result: { value: { first: seen[0] ?? {} } } };
await sleep(1500);
const late = await send("Runtime.evaluate", { expression: STATE, returnByValue: true });

/* hover 第一张卡 */
const rectRes = await send("Runtime.evaluate", {
  expression: `(() => { const r = document.querySelector('.rws-stage').getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height}; })()`,
  returnByValue: true,
});
const r = rectRes.result.value;
await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: r.x + r.w * 0.25, y: r.y + r.h * 0.25 });
await sleep(300);

const hovered = await send("Runtime.evaluate", {
  expression: `(() => {
    const c = document.querySelector('.rws-stage .rws-card');
    return {
      ax: c.style.getPropertyValue('--rws-ax'),
      nx: c.style.getPropertyValue('--rws-nx'),
      transform: c.style.transform,
      live: c.classList.contains('rws-live'),
    };
  })()`,
  returnByValue: true,
});

console.log("首帧:", JSON.stringify(early.result.value));
console.log("稳态:", JSON.stringify(late.result.value));
console.log("hover:", JSON.stringify(hovered.result.value));

let pass = true;
const check = (cond, msg) => {
  console.log(`  ${cond ? "✓" : "✗"} ${msg}`);
  if (!cond) pass = false;
};
console.log("\n=== 判定 ===");
check(late.result.value.count === 8, "8 张卡全部渲染");
check(sawIntermediate, "首帧 thumb 可见、无分层、无 rainbow（中间态被抓到）");
check(late.result.value.first.thumbHidden === true && late.result.value.first.rainbow === true,
  "稳态切分层 + rainbow");
check(hovered.result.value.transform !== "" && hovered.result.value.ax !== "", "hover 视差生效");
check(hovered.result.value.live === true, "交互期 live 类");
check(late.result.value.major18Number === false, "major-18 缺 number 不渲染");
check(late.result.value.cups3Title === false, "cups-3 缺 title 不渲染");

console.log(pass ? "\n✓ 全部通过" : "\n✗ 有失败项");
ws.close();
chrome.kill();
process.exit(pass ? 0 : 1);
