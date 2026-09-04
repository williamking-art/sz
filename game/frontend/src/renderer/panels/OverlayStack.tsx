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
import CodexPanel from "./CodexPanel";
import FocusPanel from "./FocusPanel";
import DiplomacyPanel from "./DiplomacyPanel";
import PopPanel from "./PopPanel";
import PlaceholderPanel from "./PlaceholderPanel";

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
    <div className="fixed inset-0 z-50 pointer-events-none">
      {overlays.map((ov, i) => {
        const canClose = ov.dismissible !== false;
        return (
          <div
            key={ov.id}
            className="fixed inset-0 flex items-center justify-center pointer-events-auto"
            style={{ zIndex: 100 + i * 10 }}
          >
            {/* 全屏半透明遮罩 (点击空白关闭浮层) */}
            <div
              className="absolute inset-0 bg-black/60 backdrop-blur-[2px] cursor-pointer"
              onClick={canClose ? () => popTo(i) : undefined}
            />
            {/* 弹窗实体卡片：织锦底纹 + 鎏金边框（置于遮罩之上 z-10，完全捕获事件） */}
            <div className="panel-brocade relative z-10 pointer-events-auto flex max-h-[85vh] w-[min(660px,92vw)] flex-col rounded-[4px] animate-card-in select-text">
              {/* 题头：卷轴织锦横幅 */}
              <div className="panel-titlebar flex items-center justify-between px-5 py-3">
                <span className="font-kai text-[19px] tracking-[0.22em] text-[#f0d9a8]">{ov.title}</span>
                {canClose && (
                  <button
                    onClick={() => popTo(i)}
                    aria-label="关闭"
                    className="rounded border border-gold/40 bg-black/30 p-1 text-gold transition hover:border-gold hover:bg-gold/20 hover:text-[#f0d9a8]"
                  >
                    <X size={18} />
                  </button>
                )}
              </div>
              {/* 内容：暗纸底 */}
              <div className="panel-content-dark flex-1 overflow-y-auto p-5">
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
    case "audience":
      return <MinistersPanel />;
    case "gazette":
      return <GazettePanel />;
    case "todo":
      return <TodoPanel />;
    case "personal":
      return <PersonalPanel />;
    case "prefecture":
      return <PrefecturePanel props={props as any} />;
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
    case "codex":
      return <CodexPanel props={props as any} />;
    case "focus":
      return <FocusPanel />;
    case "diplomacy":
      return <DiplomacyPanel />;
    case "pop":
      return <PopPanel />;
    default:
      return <PlaceholderPanel kind={kind} />;
  }
}