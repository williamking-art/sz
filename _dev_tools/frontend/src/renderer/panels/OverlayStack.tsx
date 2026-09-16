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
import SecretDecreePanel from "./SecretDecreePanel";
import LandPanel from "./LandPanel";
import DailyLogPanel from "./DailyLogPanel";
import CentralOrgPanel from "./CentralOrgPanel";
import GovernanceHub from "./GovernanceHub";
import AudienceView from "./AudienceView";
import PendingActionsPanel from "./PendingActionsPanel";
import MeterPanel from "./MeterPanel";
import IntroPanel from "./IntroPanel";
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
        
        // 特殊通道：若为御前召对 (kind === "audience")，直接走全屏殿堂无缝沉浸层
        if (ov.kind === "audience") {
          return (
            <div
              key={ov.id}
              className="fixed inset-0 z-50 pointer-events-auto"
              style={{ zIndex: 100 + i * 10 }}
            >
              <AudienceView props={ov.props} />
            </div>
          );
        }

        return (
          <div
            key={ov.id}
            className="fixed inset-0 flex items-center justify-center pointer-events-auto"
            style={{ zIndex: 100 + i * 10 }}
          >
            {/* 全屏半透明遮罩 (点击空白关闭浮层) */}
            <div
              className="absolute inset-0 bg-black/65 backdrop-blur-[3px] cursor-pointer"
              onClick={canClose ? () => popTo(i) : undefined}
            />
            {/* 弹窗实体卡片 (必须置于遮罩之上 z-10，完全捕获鼠标与键盘事件) */}
            <div className="relative z-10 pointer-events-auto flex max-h-[88vh] w-[min(720px,94vw)] flex-col sz-panel select-text animate-card-in">
              {/* 题头 */}
              <div className="sz-panel-header">
                <div className="flex items-center gap-2 min-w-0">
                  <img src="/images/seal_imperial.png" alt="" className="sz-seal shrink-0" />
                  <span className="sz-panel-title truncate">{ov.title}</span>
                </div>
                {canClose && (
                  <button
                    onClick={() => popTo(i)}
                    aria-label="关闭"
                    className="rounded p-1.5 text-ink-light transition hover:bg-gold-light hover:text-ink"
                  >
                    <X size={20} />
                  </button>
                )}
              </div>
              {/* 内容 */}
              <div className="sz-panel-body flex-1 overflow-y-auto text-[14.5px]">
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
    case "audience":
      return <AudienceView props={props} />;
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
    case "secretdecree":
      return <SecretDecreePanel />;
    case "land":
      return <LandPanel />;
    case "dailylog":
      return <DailyLogPanel />;
    case "centralorg":
      return <CentralOrgPanel />;
    case "governance":
      return <GovernanceHub />;
    case "pending":
      return <PendingActionsPanel />;
    case "meter":
      return <MeterPanel />;
    case "intro":
      return <IntroPanel />;
    default:
      return <PlaceholderPanel kind={kind} />;
  }
}