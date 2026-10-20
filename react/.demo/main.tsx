import React from "react";
import { createRoot } from "react-dom/client";
import { TarotCard } from "../src/TarotCard";

/* 演示卡片：覆盖有/无 number、有/无 title 四种层构成 */
const CARDS: Array<[string, string]> = [
  ["major-0", "00 愚者（四层齐全）"],
  ["major-18", "18 月亮（缺 number）"],
  ["major-21", "21 世界"],
  ["wands-1", "权杖一（有 title）"],
  ["cups-3", "圣杯三（无 title）"],
  ["pentacles-3", "星币三（缺 number）"],
  ["swords-10", "宝剑十（无 title）"],
  ["pentacles-14", "星币国王"],
];

function App() {
  return (
    <div className="grid">
      {CARDS.map(([id, label]) => (
        <div className="cell" key={id}>
          <TarotCard cardId={id} basePath="./card-assets" label={label} />
          <p>{label}</p>
        </div>
      ))}
    </div>
  );
}

createRoot(document.getElementById("grid")!).render(<App />);
