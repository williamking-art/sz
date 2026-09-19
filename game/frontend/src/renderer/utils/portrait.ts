// 立绘 URL 统一解析（2026-09-19 整改，依据 analysis/portrait_system_design.md §七）
//
// 后端已改为**受控路由** `/api/portrait/<file>`（合成图留在后端缓存目录、不写
// frontend/public）。故此处统一：以 `/` 开头者视为服务端 URL **直接使用**；
// 其余（历史静态资产，如 `general.png`）仍拼前端 `./portraits/` 前缀。
//
// 所有面板一律经本函数取图，不得各自拼 URL（为后续统一 MinisterPortrait 组件铺路）。
export function portraitSrc(p?: string | null): string {
  const s = typeof p === "string" ? p.trim() : "";
  if (!s) return "";
  if (s.startsWith("/") || /^https?:\/\//i.test(s)) return s;
  return `./portraits/${s}`;
}