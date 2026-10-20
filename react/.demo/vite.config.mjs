import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

/* 演示用 Vite 配置。
   node_modules 装在 .demo/ 里，而 root 是上一层（为了能直接引用 src/ 与 assets/），
   所以必须显式把 react 指到 .demo/node_modules，否则 Rollup 解析不到。 */
const here = import.meta.dirname;
const nm = (m) => path.resolve(here, "node_modules", m);

export default defineConfig({
  root: path.resolve(here, ".."),
  plugins: [react()],
  base: "./",
  resolve: {
    alias: {
      react: nm("react"),
      "react-dom": nm("react-dom"),
      "react/jsx-runtime": nm("react/jsx-runtime"),
      "react/jsx-dev-runtime": nm("react/jsx-dev-runtime"),
      "react-dom/client": nm("react-dom/client"),
    },
  },
  build: {
    outDir: path.resolve(here, "../demo-dist"),
    emptyOutDir: true,
    rollupOptions: {
      input: path.resolve(here, "../demo.html"),
    },
  },
  publicDir: false,
});
