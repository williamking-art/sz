// 构建期脚本：将 game/assets/map/web/ 的 geojson 平移并拓扑化为 topojson
// 用法：npm run build:topo
// 输出：frontend/public/map/*.topojson（含 view.json 与 tiles 平移）
import {
  mkdirSync, copyFileSync, readFileSync, writeFileSync, existsSync,
  readdirSync, statSync
} from "fs";
import { join, resolve } from "path";
import { topology } from "topojson-server";

// frontend 根(game/frontend);资产在上邻 game/assets/map/web
// (前端目录移入 game/ 后,__dirname 上两级即 game,不再有 game/ 二级前缀)
const ROOT = resolve(__dirname, "..");
const SRC = resolve(__dirname, "../../assets/map/web");
const DST = resolve(__dirname, "../public/map");

// 需拓扑化的政区/势力（多边形）
const TOPO_LAYERS = ["circuits", "regimes", "circuit_borders", "regime_borders"];
// 保持 geojson 平移的图层
const COPY_LAYERS = ["land", "rivers", "lakes", "cities"];

function main() {
  mkdirSync(DST, { recursive: true });

  // 1) 拓扑化政区/势力
  const objects: Record<string, unknown> = {};
  for (const name of TOPO_LAYERS) {
    const src = join(SRC, `${name}.geojson`);
    if (!existsSync(src)) {
      console.warn(`[topo] 跳过缺失 ${name}.geojson`);
      continue;
    }
    objects[name] = JSON.parse(readFileSync(src, "utf-8"));
  }
  if (Object.keys(objects).length) {
    const topo = topology(objects as never);
    writeFileSync(join(DST, "regions.topojson"), JSON.stringify(topo));
    console.log("[topo] 已生成 regions.topojson");
  }

  // 2) 平移其余 geojson
  for (const name of COPY_LAYERS) {
    const src = join(SRC, `${name}.geojson`);
    if (!existsSync(src)) continue;
    copyFileSync(src, join(DST, `${name}.geojson`));
  }

  // 3) 平移 view.json
  const viewSrc = join(SRC, "view.json");
  if (existsSync(viewSrc)) copyFileSync(viewSrc, join(DST, "view.json"));

  // 4) 平移地形瓦片（若存在）
  const tilesSrc = join(SRC, "tiles");
  if (existsSync(tilesSrc)) {
    copyDir(tilesSrc, join(DST, "tiles"));
    console.log("[topo] 已平移 tiles/");
  }

  console.log("[topo] 完成 →", DST);
}

function copyDir(src: string, dst: string) {
  mkdirSync(dst, { recursive: true });
  for (const entry of readdirSync(src)) {
    const s = join(src, entry);
    const d = join(dst, entry);
    if (statSync(s).isDirectory()) copyDir(s, d);
    else copyFileSync(s, d);
  }
}

main();