// 展示层格式化工具（对齐 game/ui/gui_common.py，保证双轨数值表述一致）

/** 整数千分位（四舍五入）。 */
export function group(n: number): string {
  return Math.round(n).toLocaleString("en-US");
}

/** 大数万表述：≥1万 → 「X万单位」；<1万 → 千分位真实数。单位为空时不带后缀。 */
export function wan(n: number | null | undefined, unit = ""): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const neg = n < 0 ? "-" : "";
  const a = Math.abs(n);
  if (a >= 10_000) {
    const w = a / 10_000;
    if (w >= 100) return `${neg}${Math.round(w)}万${unit}`;
    const s = w.toFixed(1).replace(/\.0$/, "").replace(/(\.\d)0$/, "$1");
    return `${neg}${s}万${unit}`;
  }
  return `${neg}${group(a)}${unit}`;
}

/** 货币：后台单位=贯，展示 ≥1万 换算为万贯。 */
export function humanizeCoin(guan: number | null | undefined): string {
  return wan(guan ?? 0, "贯");
}

/** 季节名：12/1/2 冬，3/4/5 春，6/7/8 夏，其余秋。 */
export function seasonName(month: number): string {
  if ([12, 1, 2].includes(month)) return "冬";
  if ([3, 4, 5].includes(month)) return "春";
  if ([6, 7, 8].includes(month)) return "夏";
  return "秋";
}

/** 古意纪年：年号·年份·季节·月份朔日。 */
export function formatEra(eraName: string, year: number, month: number): string {
  return `${eraName}${year}年·${seasonName(month)}·${month}月朔日`;
}

/** 状态取色：≥65 吉 / ≥55 平 / ≥45 警 / 否则 急（对齐 theme.status_color 阈值）。 */
export function statusColor(v: number): string {
  if (v >= 65) return "#5a7a3c";
  if (v >= 55) return "#8f6e28";
  if (v >= 45) return "#caa24a";
  return "#8a2b22";
}
