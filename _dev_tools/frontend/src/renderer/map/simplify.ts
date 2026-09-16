import { feature } from "topojson-client";
import { presimplify, simplify, quantile, filterWeight } from "topojson-simplify";

// 运行时按 zoom 分级简化：低 zoom 用粗档（少顶点、快渲染），高 zoom 逐步细化。
// topojson-simplify：加载时预计算权重（presimplify），运行时按档位零成本切换。
// 注：topojson-simplify 期望 Topology<Objects<{}>>，与全局 TopoJSON.Topology 的
// GeoJsonProperties 泛型不兼容，内部用 any 桥接，对外只暴露 GeoJSON.FeatureCollection。

/** 顶点保留比例(由粗到细);0 = 不简化,原始精度。
 *  低 zoom 保持狠简(屏幕 1px≈数十公里,细节无意义);
 *  中高 zoom 放宽:此前 0.08/0.03 会把自然路界简化成大直线。 */
export const TIERS = [0.35, 0.3, 0.25, 0.15, 0];

/** 档位索引：zoom 越高越细。 */
export function tierForZoom(zoom: number): number {
  if (zoom < 3.6) return 0;
  if (zoom < 4.6) return 1;
  if (zoom < 5.6) return 2;
  if (zoom < 6.6) return 3;
  return 4;
}

/**
 * 按 zoom 解码图层几何，并对同一 (layer, tier) 结果做缓存。
 * 缩放过程中档位不变时零开销，跨档时才重新解码一次。
 */
export class SimplifyCache {
  private topo: any;
  private cache = new Map<string, GeoJSON.FeatureCollection>();

  constructor(topology: TopoJSON.Topology) {
    // presimplify 就地附加弧段权重（幂等，重复调用无副作用）
    this.topo = presimplify(topology as any) as any;
  }

  /** 取图层在给定 zoom 下的几何数据。 */
  get(layer: string, zoom: number): GeoJSON.FeatureCollection {
    const tier = tierForZoom(zoom);
    const key = `${layer}@${tier}`;
    const hit = this.cache.get(key);
    if (hit) return hit;

    const q = TIERS[tier];
    let topo = this.topo;
    let filter: ((ring: number[][]) => boolean) | null = null;
    if (q > 0) {
      const minWeight = quantile(topo, q);
      topo = simplify(topo, minWeight) as any;
      // 丢弃简化后退化/过小的环，避免低 zoom 出现杂点
      filter = filterWeight(topo, minWeight) as any;
    }
    const fc = (feature as any)(
      topo,
      topo.objects[layer],
      filter ?? undefined
    ) as unknown as GeoJSON.FeatureCollection;
    this.cache.set(key, fc);
    return fc;
  }

  clear(): void {
    this.cache.clear();
  }
}
