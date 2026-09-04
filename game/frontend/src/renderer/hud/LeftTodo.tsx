import { useGameStore, hudTodos } from "../store/gameStore";
import { statusColor } from "../utils/format";

// 左侧常驻在办栏：宣纸卡片，描金标题「在办」
// 数据源与呈现对齐 game/ui/panels_core.py::_refresh_left_card（longterm_public + longterm_secret）
export default function LeftTodo() {
  const state = useGameStore((s) => s.state);
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const todos = hudTodos(state);

  return (
    <div className="pointer-events-auto absolute left-3 top-[92px] z-20 w-[220px]">
      <div className="rounded-[3px] border border-gold bg-card shadow-paper">
        <div className="border-b border-border px-3 py-1.5">
          <span className="font-kai text-[15px] tracking-[0.2em] text-ink">在 办</span>
        </div>
        <ul className="px-1.5 py-1">
          {todos.map((t, i) => (
            <li key={i}>
              <button
                onClick={() => pushOverlay(t.isFocus ? { kind: "focus", title: "国策大计" } : { kind: "todo", title: "在办事务" })}
                className={`group flex w-full items-center gap-2 rounded px-1.5 py-1 text-left transition ${
                  t.isFocus ? "bg-red/5 hover:bg-red/10 border border-red/20 my-0.5" : "hover:bg-gold-light"
                }`}
              >
                <span className={`flex-1 truncate text-[12px] leading-snug ${t.isFocus ? "font-bold text-red" : "text-ink"}`}>
                  {t.label}
                </span>
                <span className="h-2 w-[60px] shrink-0 overflow-hidden rounded-sm bg-[#e0d3b3]">
                  <span
                    className="block h-full rounded-sm transition-all"
                    style={{
                      width: `${Math.min(100, Math.round(t.progress * 0.6))}%`,
                      backgroundColor: t.isFocus ? "#a93226" : statusColor(t.progress)
                    }}
                  />
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}