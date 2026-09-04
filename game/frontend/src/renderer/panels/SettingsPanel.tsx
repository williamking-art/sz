import { useEffect, useState } from "react";
import { Loader2, Save, FolderOpen, Bot, Home, SlidersHorizontal } from "lucide-react";
import { getApiClient, type AiConfigResult } from "../api/client";
import { useGameStore } from "../store/gameStore";

// 设置 —— 对齐 game/ui/panels_meta.py::_panel_settings（L82）+ _panel_ai_config（L328）
// 聚合入口：存档/加载（跳转 save 面板）/ AI 配置 / 主菜单 / 杂项（音量字体为 Tk 本地配置，Web 端以说明代替）。
type Dict = Record<string, unknown>;

function asStr(v: unknown, def = ""): string {
  return typeof v === "string" ? v : def;
}

function EntryButton({
  icon, text, onClick
}: {
  icon: React.ReactNode;
  text: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center justify-center gap-3 rounded-lg bg-red px-10 py-3 font-kai text-base tracking-[0.3em] text-paper transition hover:bg-red-dark"
    >
      {icon}
      {text}
    </button>
  );
}

export default function SettingsPanel({ props }: { props?: { initialView?: "ai" | "menu" | "misc" } }) {
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const popOverlay = useGameStore((s) => s.popOverlay);
  const clearOverlays = useGameStore((s) => s.clearOverlays);
  const setInGame = useGameStore((s) => s.setInGame);
  const isDirectAi = props?.initialView === "ai";
  const [view, setView] = useState<"menu" | "ai" | "misc">(props?.initialView || "menu");

  return (
    <div className="space-y-4">
      {view === "menu" ? (
        <>
          <div className="mx-auto flex max-w-xs flex-col gap-4 py-6">
            <EntryButton icon={<Save size={18} />} text="存 档" onClick={() => pushOverlay({ kind: "save", title: "存档 · 读档" })} />
            <EntryButton icon={<FolderOpen size={18} />} text="加 载" onClick={() => pushOverlay({ kind: "save", title: "存档 · 读档" })} />
            <EntryButton icon={<Bot size={18} />} text="AI 配 置" onClick={() => setView("ai")} />
            <EntryButton icon={<Home size={18} />} text="返 回 主 单" onClick={() => { clearOverlays(); setInGame(false); }} />
            <EntryButton icon={<SlidersHorizontal size={18} />} text="杂 项" onClick={() => setView("misc")} />
          </div>
        </>
      ) : view === "ai" ? (
        <AiConfigView onBack={() => isDirectAi ? popOverlay() : setView("menu")} isDirect={isDirectAi} />
      ) : (
        <MiscView onBack={() => setView("menu")} />
      )}
    </div>
  );
}

// ---- AI 配置（对齐 _panel_ai_config）----
function AiConfigView({ onBack, isDirect }: { onBack: () => void; isDirect?: boolean }) {
  const [cfg, setCfg] = useState<AiConfigResult | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await getApiClient().getAiConfig();
        if (!alive) return;
        setCfg(res);
        setBaseUrl(res.base_url ?? "");
        setModel(res.model ?? "");
      } catch (e) {
        console.error("[ai_config]", e);
        if (alive) setMsg("读取配置失败：" + (e instanceof Error ? e.message : String(e)));
      }
    })();
    return () => { alive = false; };
  }, []);

  async function save() {
    if (busy) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await getApiClient().setAiConfig(apiKey.trim(), baseUrl.trim(), model.trim());
      setMsg(res.ok ? (res.available ? "AI 已接入，叙事推演可用。" : "已保存，但 AI 不可用（请检查密钥/地址/模型）。") : "保存失败。");
    } catch (e) {
      console.error("[setAiConfig]", e);
      setMsg("保存失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="font-kai text-lg font-bold tracking-[0.2em] text-red">AI 配 置</p>
        <button
          onClick={onBack}
          className="rounded-lg bg-paper/60 px-3 py-1.5 text-sm text-ink transition hover:bg-gold-light"
        >
          返回
        </button>
      </div>
      <p className="text-sm leading-relaxed text-dim">
        接入 OpenAI 兼容 API 后，廷议会签、大臣奏对、终局史评等叙事由 AI 推演；未接入时以规则意见代替。
      </p>
      <div className="space-y-3 rounded-lg border border-gold/40 bg-paper/60 p-4">
        <div className="flex items-center gap-3">
          <span className="w-24 shrink-0 text-sm text-ink-light">API Key</span>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={cfg?.configured ? `已配置（${cfg.api_key_masked}），留空则不改` : "sk-…"}
            className="flex-1 rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-ink outline-none focus:border-gold"
          />
        </div>
        <div className="flex items-center gap-3">
          <span className="w-24 shrink-0 text-sm text-ink-light">Base URL</span>
          <input
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://api.openai.com/v1"
            className="flex-1 rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-ink outline-none focus:border-gold"
          />
        </div>
        <div className="flex items-center gap-3">
          <span className="w-24 shrink-0 text-sm text-ink-light">模型</span>
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="gpt-4o-mini"
            className="flex-1 rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-ink outline-none focus:border-gold"
          />
        </div>
        <div className="flex justify-end">
          <button
            onClick={save}
            disabled={busy}
            className="flex items-center gap-2 rounded-lg bg-red px-6 py-2 font-kai text-sm tracking-widest text-paper transition hover:bg-red-dark disabled:opacity-60"
          >
            {busy && <Loader2 size={14} className="animate-spin" />}
            {busy ? "保存中…" : "保 存 配 置"}
          </button>
        </div>
        {msg && <p className="text-sm leading-relaxed text-ink">{msg}</p>}
      </div>
    </div>
  );
}

// ---- 杂项（Tk 本地音量/字体配置，Web 端说明）----
function MiscView({ onBack }: { onBack: () => void }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="font-kai text-lg font-bold tracking-[0.2em] text-red">杂 项</p>
        <button
          onClick={onBack}
          className="rounded-lg bg-paper/60 px-3 py-1.5 text-sm text-ink transition hover:bg-gold-light"
        >
          返回
        </button>
      </div>
      <div className="space-y-3 rounded-lg border border-gold/40 bg-paper/60 p-4">
        <p className="font-kai text-sm font-bold text-ink">声 音</p>
        <p className="text-sm leading-relaxed text-dim">
          音频系统尚未接入，调节暂不影响实际声音（预留）。
        </p>
        <p className="font-kai text-sm font-bold text-ink">字 体</p>
        <p className="text-sm leading-relaxed text-dim">
          Web 版界面字体随系统与浏览器设置（楷体优先，缺失时回退宋体/系统字体）。
        </p>
      </div>
    </div>
  );
}
