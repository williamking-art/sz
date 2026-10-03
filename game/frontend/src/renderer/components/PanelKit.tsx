import type { ReactNode } from "react";

// 宋式装饰组件库（UI 升级 · 2026-09-29）
// 把 theme.css 的 sz-panel / sz-card / 描金 / 朱印 系统封装成可复用组件，
// 消除「裸 rounded-lg border」卡片的简陋感。

/** 面板外壳：宣纸 + 双线描金 + 题头饰带 */
export function PanelShell({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="sz-panel rounded-lg">
      <div className="sz-panel-header">
        <div>
          <p className="sz-panel-title">{title}</p>
          {subtitle && (
            <p className="mt-0.5 text-xs text-ink-light opacity-70">{subtitle}</p>
          )}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
      <div className="sz-panel-body">{children}</div>
    </div>
  );
}

/** 章节标题：描金分隔线 + 楷体小标 */
export function SectionHead({
  text,
  hint,
  tone = "gold",
}: {
  text: string;
  hint?: string;
  tone?: "gold" | "red" | "ink" | "emerald";
}) {
  const lineColor =
    tone === "red"
      ? "bg-red/50"
      : tone === "ink"
        ? "bg-ink/30"
        : tone === "emerald"
          ? "bg-emerald-600/50"
          : "bg-gold/60";
  return (
    <div className="mb-2 flex items-center gap-2.5">
      <span className={`h-[2px] w-8 rounded-full ${lineColor}`} />
      <span className="font-kai text-[13px] font-bold tracking-[0.25em] text-red">
        {text}
      </span>
      <span className={`h-[2px] flex-1 rounded-full ${lineColor} opacity-40`} />
      {hint && (
        <span className="shrink-0 text-[11px] text-dim opacity-70">{hint}</span>
      )}
    </div>
  );
}

/** 数据卡：宣纸底 + 描金框 + 大数字 */
export function StatCard({
  label,
  value,
  unit,
  tone = "ink",
  sub,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  tone?: "ink" | "red" | "gold" | "emerald";
  sub?: string;
}) {
  const toneCls =
    tone === "red"
      ? "text-red"
      : tone === "gold"
        ? "text-gold-dark"
        : tone === "emerald"
          ? "text-emerald-700"
          : "text-ink";
  return (
    <div className="sz-card rounded-md p-2.5 text-center">
      <p className="text-[11px] tracking-wider text-dim">{label}</p>
      <p className={`mt-1 font-sans text-lg font-bold leading-tight ${toneCls}`}>
        {value}
        {unit && <span className="ml-0.5 text-xs font-normal opacity-70">{unit}</span>}
      </p>
      {sub && <p className="mt-0.5 text-[10px] text-dim opacity-70">{sub}</p>}
    </div>
  );
}

/** 描金分隔线 */
export function GoldDivider({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <span className="h-px flex-1 bg-gradient-to-r from-transparent via-gold/50 to-transparent" />
      <span className="text-[10px] text-gold-dark opacity-50">❖</span>
      <span className="h-px flex-1 bg-gradient-to-r from-transparent via-gold/50 to-transparent" />
    </div>
  );
}

/** 分幕小剧场卡片（众生相） */
export function SceneCard({
  scene,
  text,
  tone = "red",
}: {
  scene: string;
  text: string;
  tone?: "red" | "emerald" | "ink" | "gold";
}) {
  const borderCls =
    tone === "emerald"
      ? "border-l-emerald-600/50"
      : tone === "ink"
        ? "border-l-ink/40"
        : tone === "gold"
          ? "border-l-gold/60"
          : "border-l-red/50";
  return (
    <div className={`border-l-2 ${borderCls} pl-3 py-1`}>
      <p className="font-kai text-[12px] font-bold text-ink">
        【{scene}】
      </p>
      <p className="mt-0.5 text-[13px] leading-relaxed text-ink-light">{text}</p>
    </div>
  );
}

/** 状态徽章（风险/危急/档位） */
export function Badge({
  text,
  tone = "gold",
}: {
  text: string;
  tone?: "gold" | "red" | "emerald" | "ink";
}) {
  const cls =
    tone === "red"
      ? "bg-red text-paper"
      : tone === "emerald"
        ? "bg-emerald-700 text-paper"
        : tone === "ink"
          ? "bg-ink/80 text-paper"
          : "bg-gold text-ink";
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-[11px] font-bold ${cls}`}>
      {text}
    </span>
  );
}

/** 朱印标注（装饰性） */
export function Seal({ text }: { text: string }) {
  return (
    <span className="inline-flex h-7 w-7 items-center justify-center rounded-sm border-[1.5px] border-gold bg-red text-[10px] font-bold leading-none text-paper shadow-sm">
      {text.slice(0, 2)}
    </span>
  );
}
