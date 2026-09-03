import { Delaunay } from "d3-delaunay";

// 标签避让：屏幕空间碰撞剔除（d3-delaunay 加速近邻查询）
// 优先级高（档位低/京府/治所）的标签先占位，与之重叠的低优先标签本帧隐藏。
// 视口变化后调用（防抖），不做逐帧计算。

export interface AvoidBox {
  key: number;
  x: number;
  y: number;
  w: number;
  h: number;
  priority: number; // 越小越重要
}

/**
 * 计算应隐藏的标签 key 集合。
 * @param boxes 视口内候选标签包围盒（屏幕坐标，中心 x/y + 宽高）
 * @param radius 近邻搜索半径（px），默认取最长标签宽度的量级
 */
export function computeHidden(boxes: AvoidBox[], radius = 90): Set<number> {
  const hidden = new Set<number>();
  if (boxes.length < 2) return hidden;

  // 按优先级（重要在前）排序，重要的先占位
  const sorted = [...boxes].sort((a, b) => a.priority - b.priority);

  // d3-delaunay 建索引，供邻域查询
  const points = sorted.map((b) => [b.x, b.y] as [number, number]);
  const delaunay = Delaunay.from(points);
  const placed: AvoidBox[] = [];

  for (let i = 0; i < sorted.length; i++) {
    const box = sorted[i];
    // 邻域内逐个比对（delaunay 提供候选，实际判重用 AABB 相交）
    let collide = false;
    for (const j of delaunay.neighbors(i)) {
      const other = sorted[j];
      if (hidden.has(other.key)) continue;
      if (!placed.some((p) => p.key === other.key)) continue;
      if (overlap(box, other)) {
        collide = true;
        break;
      }
    }
    if (collide) {
      hidden.add(box.key);
    } else {
      // 邻域可能遗漏（半径外的大标签）：对已放置的做一次兜底扫描
      let hit = false;
      for (const p of placed) {
        if (Math.abs(p.x - box.x) > radius && Math.abs(p.y - box.y) > radius) continue;
        if (overlap(box, p)) {
          hit = true;
          break;
        }
      }
      if (hit) hidden.add(box.key);
      else placed.push(box);
    }
  }
  return hidden;
}

/** AABB 相交判定（含 1px 间隙，避免视觉贴边）。 */
function overlap(a: AvoidBox, b: AvoidBox): boolean {
  const gap = 1;
  return (
    Math.abs(a.x - b.x) * 2 < a.w + b.w + gap &&
    Math.abs(a.y - b.y) * 2 < a.h + b.h + gap
  );
}
