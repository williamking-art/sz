import type { PanelKind } from "../store/gameStore";

// 占位面板：尚未迁移的玩法面板统一占位
const LABELS: Partial<Record<PanelKind, string>> = {
  court: "朝堂议事",
  ministers: "群臣名录",
  gazette: "朝报",
  personal: "个人行止",
  prefecture: "州县治理",
  granary: "仓廪",
  accounting: "会计",
  military: "军政",
  tech: "科技",
  engineering: "工程",
  settings: "设置",
  save: "存档",
  newgame: "开局",
  conclude: "终局评估",
  todo: "在办事务"
};

export default function PlaceholderPanel({ kind }: { kind: PanelKind }) {
  const label = LABELS[kind] ?? "功能";
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-3 font-kai text-2xl tracking-widest text-ink">{label}</div>
      <p className="text-sm text-ink-light">该面板正在迁移中，敬请期待。</p>
    </div>
  );
}