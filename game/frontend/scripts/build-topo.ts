// 构建期脚本：将 game/assets/map/web/ 的 geojson 平移并拓扑化为 topojson
// 用法：npm run build:topo
// 输出：frontend/public/map/*.topojson（含 view.json 与 tiles 平移）
import {
  mkdirSync, copyFileSync, readFileSync, writeFileSync, existsSync,
  readdirSync, statSync
} from "fs";
import { join, resolve } from "path";
import { topology } from "topojson-server";

// `@types/topojson-server` 的签名只声明 1 个参数，而 topojson-server v3 运行时**支持**
// `topology(objects, quantization)`（其 README 明确）。此处按运行时契约收窄一次，
// 避免为传量化参数而在调用点铺 `any`。
const topologyQ = topology as unknown as (objects: unknown, quantization?: number) => unknown;

// 目录结构现状：<repo>/game/frontend/scripts → 资产在 <repo>/game/assets/map/web
// （__dirname 上三级即仓库根；曾按 frontend 位于 game/ 下的旧结构写死，已按实际修正）
const ROOT = resolve(__dirname, "..");
const SRC = resolve(__dirname, "../../../game/assets/map/web");
const DST = resolve(__dirname, "../public/map");

// 需拓扑化的政区/势力（多边形）
const TOPO_LAYERS = ["circuits", "regimes", "circuit_borders", "regime_borders"];
// 府级（州府）边界 —— **独立拓扑文件**（P1-2 接入，2026-09-27）。
// 刻意不并入 `regions.topojson`：那会把首帧 `JSON.parse` 的成本从 13.0 MB 推到 25 MB+
// （见 MapView 首帧基准注释），而府界只在 zoom ≥ 5.2 才可见 → 单独产出、前端**懒加载**。
const PREFECTURE_TOPO_LAYERS = ["prefecture_borders"];
/** 府界拓扑**量化格**。实测（2026-09-27）：不量化 18.42 MB → `1e5` **2.73 MB**、
 *  `1e4` 1.30 MB。取 `1e5`（格距 ≈0.0006°≈69 m；地图最大 zoom 9 时约 0.2 px）——
 *  体积极小且线形在可见档位无肉眼差异；`1e4` 在 zoom 8+ 会出现 ~1 px 阶梯。 */
const PREFECTURE_QUANTIZATION = 1e5;
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

  // 1b) 府级边界（独立文件，供前端懒加载）
  const prefObjects: Record<string, unknown> = {};
  for (const name of PREFECTURE_TOPO_LAYERS) {
    const src = join(SRC, `${name}.geojson`);
    if (!existsSync(src)) {
      console.warn(`[topo] 跳过缺失 ${name}.geojson（府级边界将不可用）`);
      continue;
    }
    prefObjects[name] = JSON.parse(readFileSync(src, "utf-8"));
  }
  if (Object.keys(prefObjects).length) {
    const topo = topologyQ(prefObjects, PREFECTURE_QUANTIZATION);
    writeFileSync(join(DST, "prefecture_borders.topojson"), JSON.stringify(topo));
    console.log("[topo] 已生成 prefecture_borders.topojson（quantization="
      + PREFECTURE_QUANTIZATION + "）");
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

  // 4) 地形瓦片：**当前不存在**（`public/map/tiles/hill/` 目录缺失，需联网跑
  //    `game/fetch_hillshade.py` 才能生成；脚本只产 z5–7，而源声明 z4–8）。
  //    前端由 `layers.HILL_TILES_ENABLED=false` 不声明 hill 源，避免每块瓦片持续 404。
  //    （原注释称"瓦片已直接常驻 frontend/public/map/tiles/"，与事实相反，已据实修正。）
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