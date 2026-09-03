import { useEffect } from "react";
import { X } from "lucide-react";
import { useGameStore, type PanelKind } from "../store/gameStore";
import AdvancePanel from "./AdvancePanel";
import DecreePanel from "./DecreePanel";
import EventPanel from "./EventPanel";
import DetailPanel from "./DetailPanel";
import StartPanel from "./StartPanel";
import CourtPanel from "./CourtPanel";
import MinistersPanel from "./MinistersPanel";
import GazettePanel from "./GazettePanel";
import TodoPanel from "./TodoPanel";
import PersonalPanel from "./PersonalPanel";
import PrefecturePanel from "./PrefecturePanel";
import GranaryPanel from "./GranaryPanel";
import AccountingPanel from "./AccountingPanel";
import MilitaryPanel from "./MilitaryPanel";
import TechPanel from "./TechPanel";
import EngineeringPanel from "./EngineeringPanel";
import SettingsPanel from "./SettingsPanel";
import SavePanel from "./SavePanel";
import ConcludePanel from "./ConcludePanel";

// 浮层栈：宣纸奏章卡片叠于舆图之上，Esc 逐层关闭（对齐 panels_core.py::_overlay_stack）
export default function OverlayStack() {
  const overlays = useGameStore((s) => s.overlays);
  const popOverlay = useGameStore((s) => s.popOverlay);
  const popTo = useGameStore((s) => s.popTo);

  // Esc：关最上层浮层；无浮层时唤出设置（对齐 Tk 版 _on_esc）
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (overlays.length === 0) return;
      if (overlays[overlays.length - 1].dismissible === false) return;
      popOverlay();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [overlays, popOverlay]);

  if (overlays.length === 0) return null;

  return (
    <div className="pointer-events-none absolute inset-0 z-30">
      {overlays.map((ov, i) => {
        const canClose = ov.dismissible !== false;
        return (
          <div
            key={ov.id}
            className="pointer-events-auto absolute inset-0 flex items-center justify-center"
            style={{ zIndex: i + 1 }}
          >
            <div
              className="absolute inset-0 bg-ink/25 backdrop-blur-[1px]"
              onClick={canClose ? () => popTo(i) : undefined}
            />
            <div className="relative flex max-h-[82vh] w-[min(640px,90vw)] flex-col rounded-[4px] border border-gold bg-card shadow-card animate-card-in">
              {/* 题头 */}
              <div className="flex items-center justify-between border-b border-gold/50 px-5 py-2.5">
                <span className="font-kai text-[19px] tracking-[0.18em] text-ink">{ov.title}</span>
                {canClose && (
                  <button
                    onClick={() => popTo(i)}
                    aria-label="关闭"
                    className="rounded p-1 text-ink-light transition hover:bg-gold-light hover:text-ink"
                  >
                    <X size={18} />
                  </button>
                )}
              </div>
              {/* 内容 */}
              <div className="flex-1 overflow-y-auto p-5">
                <PanelBody kind={ov.kind} props={ov.props} />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PanelBody({ kind, props }: { kind: PanelKind; props?: Record<string, unknown> }) {
  switch (kind) {
    case "advance":
      return <AdvancePanel props={props} />;
    case "decree":
      return <DecreePanel />;
    case "event":
      return <EventPanel props={props} />;
    case "detail":
      return <DetailPanel props={props} />;
    case "newgame":
      return <StartPanel />;
    case "court":
      return <CourtPanel />;
    case "ministers":
      return <MinistersPanel />;
    case "gazette":
      return <GazettePanel />;
    case "todo":
      return <TodoPanel />;
    case "personal":
      return <PersonalPanel />;
    case "prefecture":
      return <PrefecturePanel props={item.props as any} />;
    case "granary":
      return <GranaryPanel />;
    case "accounting":
      return <AccountingPanel />;
    case "military":
      return <MilitaryPanel />;
    case "tech":
      return <TechPanel />;
    case "engineering":
      return <EngineeringPanel />;
    case "settings":
      return <SettingsPanel />;
    case "save":
      return <SavePanel />;
    case "conclude":
      return <ConcludePanel />;
    default:
      return <PlaceholderPanel kind={kind} />;
  }
}