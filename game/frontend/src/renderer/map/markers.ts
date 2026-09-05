import maplibregl from "maplibre-gl";
import { TIER } from "./layers";
import { computeHidden, type AvoidBox } from "./avoid";
import type { Selected } from "../store/gameStore";

// 标签记录：HTML Marker + 显隐档位 + 数据侧可见性
export interface LabelRecord {
  el: HTMLElement;
  tier: number;
  visible: boolean;
  kind?: string;
  name?: string;
  parent?: string;
  owner?: string;
  marker: maplibregl.Marker;
}

export interface CustomMarker {
  lng: number;
  lat: number;
  label?: string;
  kind?: "warn" | "normal";
}

// 主次互斥组：macro（省/路名）与 micro（府/县名）同区域重叠时 macro 优先；
// zoom 深入后（≥ macro 隐没档位或避让胜出）micro 才浮现。
export interface MutualExclusion {
  macro: (lab: LabelRecord) => boolean;
  micro: (lab: LabelRecord) => boolean;
}

export class MarkerManager {
  private map: maplibregl.Map;
  private labels: (LabelRecord & { priority: number; lngLat: [number, number] })[] = [];
  private customMarkers: maplibregl.Marker[] = [];
  private pulseMarker: maplibregl.Marker | null = null;
  private exclusions: MutualExclusion[] = [];

  constructor(map: maplibregl.Map) {
    this.map = map;
  }

  /** 注册主次互斥组（如：省级路名 macro 优先于府县名 micro）。 */
  registerMutualExclusion(rule: MutualExclusion): void {
    this.exclusions.push(rule);
  }

  addLabel(
    lngLat: [number, number],
    text: string,
    cls: string,
    tier: number,
    visible: boolean,
    onClick?: () => void,
    meta?: { kind?: string; name?: string; parent?: string; owner?: string }
  ): maplibregl.Marker {
    const el = document.createElement("div");
    el.className = `lbl ${cls}`;
    el.textContent = text;
    if (onClick) {
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        onClick();
      });
    }
    const mk = new maplibregl.Marker({ element: el, anchor: "center" })
      .setLngLat(lngLat)
      .addTo(this.map);
    this.labels.push({
      el,
      tier,
      visible: visible !== false,
      kind: meta?.kind,
      name: meta?.name,
      parent: meta?.parent,
      owner: meta?.owner,
      marker: mk,
      // 优先级：档位越低（越早出现）越重要；同级按 kind 微调
      priority: tier * 10 + (meta?.kind === "regime" ? 0 : meta?.kind === "sub" ? 1 : 2),
      lngLat
    });
    return mk;
  }

  /**
   * 标签避让：视口内屏幕空间碰撞剔除（d3-delaunay 近邻）。
   * 在 moveend / 档位刷新后调用（调用方负责防抖）。
   */
  avoid(): void {
    const zoom = this.map.getZoom();
    const boxes: AvoidBox[] = [];

    // 主次互斥引擎（前置过滤）：对每个互斥组，macro（省级路名）仍在压制档位内时，
    // 与其同区域的 micro（府县名）直接不参与本帧避让——保证"有省名时不显府名"铁律。
    const suppressed = new Set<number>();
    for (const rule of this.exclusions) {
      const macroLabels = this.labels.filter((l) => rule.macro(l) && l.visible);
      if (!macroLabels.length) continue;
      const maxMacroTier = Math.max(...macroLabels.map((l) => l.tier));
      // zoom 深入超过 macro 档位 +1.2 级后停止压制（府名接班）
      if (zoom >= maxMacroTier + 1.2) continue;
      for (let i = 0; i < this.labels.length; i++) {
        const l = this.labels[i];
        if (!rule.micro(l)) continue;
        const p = this.map.project(l.lngLat);
        for (const m of macroLabels) {
          const mp = this.map.project(m.lngLat);
          // 地理同区域判定：屏幕距离 < 150px 视为路名辐射区，府县名一律退让
          if (Math.abs(p.x - mp.x) < 150 && Math.abs(p.y - mp.y) < 100) {
            l.el.classList.add("lbl-hidden");
            suppressed.add(i);
            break;
          }
        }
      }
    }

    for (let i = 0; i < this.labels.length; i++) {
      const l = this.labels[i];
      // 互斥已压制者不再参与避让
      if (suppressed.has(i)) continue;
      // 先按数据侧可见性与档位过滤
      if (!l.visible || zoom < l.tier) {
        l.el.classList.add("lbl-hidden");
        continue;
      }
      const p = this.map.project(l.lngLat);
      if (p.x < -60 || p.y < -30 || p.x > this.map.getContainer().clientWidth + 60 ||
          p.y > this.map.getContainer().clientHeight + 30) {
        l.el.classList.add("lbl-hidden"); // 视口外，无需参与避让
        continue;
      }
      const rect = l.el.getBoundingClientRect();
      // 首帧回流前 rect.width 经常为 0, 依据文字长度与字号严密估算包围盒, 彻底杜绝重合
      const textLen = (l.el.textContent || "").length;
      const isLarge = l.el.classList.contains("lbl-regime");
      const fontSize = isLarge ? 20 : 13;
      const estimatedW = textLen * fontSize + 16;
      const actualW = rect.width || l.el.offsetWidth;
      const finalW = Math.max(actualW, estimatedW);
      const finalH = Math.max(rect.height || l.el.offsetHeight, fontSize + 8);

      boxes.push({
        key: i,
        x: p.x,
        y: p.y,
        w: finalW,
        h: finalH,
        priority: l.priority
      });
    }

    // 参与避让的标签按结果显隐；未参与的（视口外/档位外/互斥压制）已在上一步隐藏
    const hidden = computeHidden(boxes);
    for (const b of boxes) {
      this.labels[b.key].el.classList.toggle("lbl-hidden", hidden.has(b.key));
    }
  }

  // 按 zoom 刷新标签显隐
  refresh(zoom: number): void {
    for (const l of this.labels) {
      const show = l.visible && zoom >= l.tier;
      l.el.classList.toggle("lbl-hidden", !show);
    }
  }

  // 政权 active 变化后同步标签可见性
  refreshRegimeLabels(
    regimeOn: Record<string, boolean>,
    subOn: (parent: string, owner: string) => boolean
  ): void {
    for (const lab of this.labels) {
      let on: boolean | undefined;
      if (lab.kind === "regime" && lab.name) on = regimeOn[lab.name];
      else if (lab.kind === "sub" && lab.parent && lab.owner) {
        on = subOn(lab.parent, lab.owner);
      } else continue;
      lab.visible = on;
      lab.el.classList.toggle("off", !on);
    }
    this.refresh(this.map.getZoom());
  }

  // 自定义朱印标注（事件/军队等）
  applyCustom(markers: CustomMarker[]): void {
    for (const m of this.customMarkers) m.remove();
    this.customMarkers = [];
    for (const m of markers || []) {
      if (!isFinite(m.lng) || !isFinite(m.lat)) continue;
      const el = document.createElement("div");
      el.className = "seal-mk";
      el.innerHTML = `<div class="sq${m.kind === "warn" ? " warn" : ""}"></div><div class="tx"></div>`;
      el.querySelector(".tx")!.textContent = m.label || "";
      const mk = new maplibregl.Marker({ element: el, anchor: "bottom" })
        .setLngLat([m.lng, m.lat])
        .addTo(this.map);
      this.customMarkers.push(mk);
    }
  }

  // 治所选中呼吸光环
  pulseAt(lngLat: [number, number]): void {
    this.clearPulse();
    const el = document.createElement("div");
    el.className = "pulse";
    this.pulseMarker = new maplibregl.Marker({ element: el, anchor: "center" })
      .setLngLat(lngLat)
      .addTo(this.map);
  }

  clearPulse(): void {
    if (this.pulseMarker) {
      this.pulseMarker.remove();
      this.pulseMarker = null;
    }
  }

  clearAll(): void {
    for (const l of this.labels) l.marker.remove();
    this.labels = [];
    for (const m of this.customMarkers) m.remove();
    this.customMarkers = [];
    this.clearPulse();
  }
}

// 标签档位导出（供外部引用）
export { TIER };
export type { Selected };