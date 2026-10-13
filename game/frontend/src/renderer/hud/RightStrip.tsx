import { useEffect, useRef, useState } from "react";
import {
  Archive, BookOpen, Building2, Calculator, ClipboardList, FileText, FlaskConical,
  Hammer, Landmark, Lock, Map, Newspaper, ScrollText, Scale, Shield, Stamp,
  Users, Warehouse, Wheat, Globe2, Flame, Trees, PenLine, UserRound, Gauge,
  ChevronRight, X
} from "lucide-react";
import { useGameStore, type PanelKind } from "../store/gameStore";

type Item = { key: PanelKind; label: string; icon: typeof Map };
type Group = { key: string; label: string; short: string; icon: typeof Map; items: Item[] };

const GROUPS: Group[] = [
  {
    key: "court", label: "朝廷中枢", short: "中枢", icon: Landmark,
    items: [
      { key: "court", label: "朝堂", icon: Landmark },
      { key: "ministers", label: "群臣", icon: Users },
      { key: "audience", label: "御前召对", icon: UserRound },
      { key: "pending", label: "批红", icon: Stamp },
      { key: "centralorg", label: "中枢机枢", icon: Building2 },
      { key: "governance", label: "治务总览", icon: ClipboardList }
    ]
  },
  {
    key: "decree", label: "政令施为", short: "政务", icon: ScrollText,
    items: [
      { key: "decree", label: "拟旨", icon: PenLine },
      { key: "secretdecree", label: "密令", icon: Lock },
      { key: "focus", label: "国策", icon: Scale },
      { key: "engineering", label: "营造工程", icon: Hammer },
      { key: "tech", label: "科技典制", icon: FlaskConical },
      { key: "personal", label: "行止", icon: ScrollText },
      { key: "todo", label: "在办事务", icon: ClipboardList }
    ]
  },
  {
    key: "realm", label: "天下诸务", short: "天下", icon: Map,
    items: [
      { key: "prefecture", label: "州县舆图", icon: Map },
      { key: "pop", label: "民生人口", icon: Wheat },
      { key: "land", label: "田亩", icon: Trees },
      { key: "granary", label: "仓廪", icon: Warehouse },
      { key: "accounting", label: "会计", icon: Calculator },
      { key: "readouthub", label: "读数索引", icon: Gauge },
      { key: "military", label: "军政", icon: Shield },
      { key: "provincemilitary", label: "经略边防", icon: Shield },
      { key: "diplomacy", label: "邦交", icon: Globe2 },
      { key: "situation", label: "时局", icon: Flame }
    ]
  },
  {
    key: "archive", label: "邸报典籍", short: "文书", icon: BookOpen,
    items: [
      { key: "gazette", label: "邸报", icon: Newspaper },
      { key: "dailylog", label: "近日机务", icon: FileText },
      { key: "memory", label: "史事记忆", icon: BookOpen },
      { key: "codex", label: "典籍", icon: BookOpen },
      { key: "localarchive", label: "本地档案", icon: Archive },
      { key: "meter", label: "词元用度", icon: Gauge }
    ]
  }
];

/** 分类职司目录：收拢原本常驻的十枚圆钮，其余所有旧入口仍在目录中可达。 */
export default function RightStrip() {
  const [openGroup, setOpenGroup] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const pushOverlay = useGameStore((s) => s.pushOverlay);

  useEffect(() => {
    if (!openGroup) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpenGroup(null);
    };
    const onPointerDown = (event: PointerEvent) => {
      if (event.target instanceof Node && !rootRef.current?.contains(event.target)) {
        setOpenGroup(null);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
    };
  }, [openGroup]);

  const selected = GROUPS.find((group) => group.key === openGroup) ?? null;
  const SelectedIcon = selected?.icon;

  return (
    <div ref={rootRef} className="pointer-events-none absolute right-4 top-1/2 z-30 -translate-y-1/2">
      <div className="pointer-events-auto relative flex flex-col items-center gap-2 rounded-[2rem] border border-[#8f6e28]/45 bg-[#f6ecd6]/90 p-2 shadow-[0_12px_36px_rgba(28,18,12,.2)] backdrop-blur-md">
        <span className="mb-0.5 font-kai text-[9px] tracking-[.24em] text-[#8f6e28] [writing-mode:vertical-rl]">职 方 图 籍</span>
        {GROUPS.map((group) => {
          const Icon = group.icon;
          const active = openGroup === group.key;
          return (
            <button
              key={group.key}
              type="button"
              aria-expanded={active}
              aria-label={group.label}
              title={group.label}
              onClick={() => setOpenGroup(active ? null : group.key)}
              className={`sz-nav-seal group flex h-[48px] w-[48px] flex-col items-center justify-center rounded-xl transition duration-200 ${
                active ? "is-active" : "hover:-translate-x-0.5"
              }`}
            >
              <Icon size={18} strokeWidth={1.7} />
              <span className="mt-0.5 font-kai text-[10px] font-bold tracking-[.08em]">{group.short}</span>
            </button>
          );
        })}
        <span className="mt-0.5 h-px w-7 bg-[#8f6e28]/40" />
        <button
          type="button"
          title="关闭目录"
          aria-label="关闭目录"
          onClick={() => setOpenGroup(null)}
          className="flex h-8 w-8 items-center justify-center rounded-full text-[#8f6e28] transition hover:bg-[#8a2b22]/10 hover:text-[#8a2b22]"
        >
          <ChevronRight size={16} />
        </button>
      </div>

      {selected && (
          <section
            aria-label={selected.label}
            className="sz-nav-drawer pointer-events-auto absolute right-[4.7rem] top-1/2 w-[min(330px,calc(100vw-6rem))] -translate-y-1/2 overflow-hidden rounded-sm"
          >
            <header className="relative flex items-center justify-between overflow-hidden px-5 py-4">
              <div className="absolute inset-0 sz-nav-landscape" aria-hidden="true" />
              <div className="relative flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center border border-[#caa24a]/80 bg-[#8a2b22] text-[#f6ecd6] shadow-sm">
                  {SelectedIcon && <SelectedIcon size={19} strokeWidth={1.6} />}
                </span>
                <div>
                  <p className="font-kai text-[17px] font-bold tracking-[.2em] text-[#f8efd9]">{selected.label}</p>
                  <p className="mt-0.5 text-[10px] tracking-[.18em] text-[#e8d49c]/80">SONG COURT · DIRECTORY</p>
                </div>
              </div>
              <button
                type="button"
                aria-label="关闭"
                onClick={() => setOpenGroup(null)}
                className="relative rounded-full border border-[#e8d49c]/35 p-1.5 text-[#f6ecd6]/80 transition hover:bg-[#f6ecd6]/10 hover:text-white"
              >
                <X size={15} />
              </button>
            </header>
            <div className="grid max-h-[min(58vh,480px)] grid-cols-2 gap-2 overflow-y-auto bg-[#f6ecd6]/95 p-3">
              {selected.items.map((item, index) => {
                const Icon = item.icon;
                return (
                  <button
                    type="button"
                    key={item.key}
                    onClick={() => {
                      setOpenGroup(null);
                      pushOverlay({ kind: item.key, title: item.label });
                    }}
                    className="sz-nav-entry group flex min-h-[58px] items-center gap-2.5 px-3 py-2 text-left"
                    style={{ animationDelay: `${index * 24}ms` }}
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center border border-[#caa24a]/50 bg-[#fffaf0] text-[#8a2b22] transition group-hover:border-[#8a2b22]/50 group-hover:bg-[#8a2b22] group-hover:text-[#f6ecd6]">
                      <Icon size={16} strokeWidth={1.75} />
                    </span>
                    <span className="font-kai text-[13px] font-semibold tracking-[.06em] text-[#2b1d12]">{item.label}</span>
                  </button>
                );
              })}
            </div>
            <footer className="flex items-center justify-between border-t border-[#caa24a]/45 bg-[#efe2c4] px-4 py-2 text-[10px] tracking-wider text-[#6d5b3c]">
              <span>大宋 · 职司总目</span>
              <span>{selected.items.length.toString().padStart(2, "0")} 项</span>
            </footer>
          </section>
      )}
    </div>
  );
}
