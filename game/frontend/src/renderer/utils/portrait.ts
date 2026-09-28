// 立绘 URL 统一解析（2026-09-19 整改；2026-09-27 修 app:// 打包态）
//
// 后端是**受控路由** `/api/portrait/<file>`（合成图留在后端缓存目录、不写 frontend/public）。
// 打包态渲染层由自定义协议 `app://songzuo` 提供，**根相对路径会落到应用源**（404，碎图）
// —— 故必须拼成**后端 origin 的绝对 URL**；base 由 App 在解析出后端地址时注入。
//
// 所有面板一律经本函数取图，不得各自拼 URL。
let _base = "";

/** 注入后端 origin（如 `http://127.0.0.1:8080`）；传空串表示清空。 */
export function setPortraitBase(base?: string | null): void {
  _base = typeof base === "string" ? base.replace(/\/+$/, "") : "";
}

export function portraitSrc(p?: string | null): string {
  const s = typeof p === "string" ? p.trim() : "";
  if (!s) return "";
  if (/^https?:\/\//i.test(s)) return s;              // 绝对 URL 原样
  if (s.startsWith("/")) return _base ? `${_base}${s}` : s;  // 服务端受控路由 → 拼后端 origin
  return `./portraits/${s}`;                            // 前端静态资产
}
