// 地图首帧成本基准：JSON.parse(13MB topojson) + 4 次 topojson feature() 提取。
// **多次迭代取 min/中位/max**——单次数字不可靠（实测同一文件两次跑出 130.7ms 与 231.8ms，
// 差异来自 JIT 预热/磁盘缓存/机器负载；用单点下结论会误导改造决策）。
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { feature } from "topojson-client";

const __dirname = dirname(fileURLToPath(import.meta.url));
const F = resolve(__dirname, "../../public/map/regions.topojson");
const buf = readFileSync(F);
const text = buf.toString("utf8");
const ITER = Number(process.env.BENCH_ITER ?? 5);
const LAYERS = ["circuits", "regimes", "circuit_borders", "regime_borders"];

const ms = (t0) => Number(process.hrtime.bigint() - t0) / 1e6;
const stat = (a) => {
  const s = [...a].sort((x, y) => x - y);
  return { min: s[0], med: s[Math.floor(s.length / 2)], max: s[s.length - 1] };
};
const fmt = (o) => `${o.min.toFixed(1)} / ${o.med.toFixed(1)} / ${o.max.toFixed(1)} ms（min/中位/max）`;

const parses = [], extracts = [], totals = [];
let last = null;
for (let i = 0; i < ITER; i++) {
  const t0 = process.hrtime.bigint();
  const topo = JSON.parse(text);
  const p = ms(t0);
  const t1 = process.hrtime.bigint();
  const fcs = LAYERS.map((n) => (topo.objects?.[n] ? feature(topo, topo.objects[n]) : null));
  const e = ms(t1);
  parses.push(p); extracts.push(e); totals.push(p + e);
  last = { topo, fcs };
}

console.log(`文件 ${(buf.length / 1048576).toFixed(1)} MB · 迭代 ${ITER} 次（V8/Node，与 Chromium 同引擎）`);
console.log(`JSON.parse : ${fmt(stat(parses))}`);
console.log(`feature()  : ${fmt(stat(extracts))}`);
console.log(`合计       : ${fmt(stat(totals))}`);
for (let i = 0; i < LAYERS.length; i++) {
  const fc = last.fcs[i];
  if (!fc) { console.log(`  ${LAYERS[i].padEnd(18)} （缺）`); continue; }
  const bytes = JSON.stringify(fc).length;
  console.log(`  ${LAYERS[i].padEnd(18)} ${String(fc.features.length).padStart(4)} 要素  GeoJSON ${(bytes / 1048576).toFixed(1)} MB`);
}
console.log("注：未含 fetch、MapLibre 建图与两个 9.3MB 多边形的索引成本——那两个量级更大但未测。");
