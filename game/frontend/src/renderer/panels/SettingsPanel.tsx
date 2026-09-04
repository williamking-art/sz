import { useEffect, useState } from "react";
import { Loader2, Bot, Volume2, CheckCircle2, AlertCircle, Sparkles } from "lucide-react";
import { getApiClient, type AiConfigResult } from "../api/client";
import { useGameStore } from "../store/gameStore";

// 常见大模型服务商预设（一键速填 Base URL 和 Model）
const PROVIDER_PRESETS = [
  {
    name: "DeepSeek (推荐)",
    baseUrl: "https://api.deepseek.com",
    model: "deepseek-chat",
    desc: "北宋叙事与朝堂推演表现极佳，成本极低"
  },
  {
    name: "OpenAI 官方",
    baseUrl: "https://api.openai.com/v1",
    model: "gpt-4o-mini",
    desc: "国际通用标准接口"
  },
  {
    name: "本地 Ollama / vLLM",
    baseUrl: "http://127.0.0.1:11434/v1",
    model: "qwen2.5:7b",
    desc: "纯本地离线运行，无需外网 Key"
  }
];

export default function SettingsPanel() {
  const [tab, setTab] = useState<"ai" | "audio">("ai");
  const popOverlay = useGameStore((s) => s.popOverlay);

  return (
    <div className="space-y-4">
      {/* 顶部直达 Tab：AI 算力与配置（默认高亮选中！） / 视听规制 */}
      <div className="flex items-center justify-between border-b border-gold/40 pb-2">
        <div className="flex gap-2">
          <button
            onClick={() => setTab("ai")}
            className={`flex items-center gap-1.5 rounded px-3 py-1 font-kai text-sm transition ${
              tab === "ai"
                ? "bg-red text-paper shadow-sm"
                : "bg-paper/70 text-ink hover:bg-gold-light/40"
            }`}
          >
            <Bot size={15} /> 枢密 AI 配置
          </button>
          <button
            onClick={() => setTab("audio")}
            className={`flex items-center gap-1.5 rounded px-3 py-1 font-kai text-sm transition ${
              tab === "audio"
                ? "bg-red text-paper shadow-sm"
                : "bg-paper/70 text-ink hover:bg-gold-light/40"
            }`}
          >
            <Volume2 size={15} /> 视听音律
          </button>
        </div>
        <span className="font-kai text-xs text-dim">
          {tab === "ai" ? "大模型接口 · 廷议叙事引擎" : "大晟府雅乐 · 环境音律规制"}
        </span>
      </div>

      {tab === "ai" ? <AiConfigDirectView onClose={popOverlay} /> : <AudioSettingsView />}
    </div>
  );
}

/** 直接呈现的 AI 配置视图（无任何中间过渡按钮！） */
function AiConfigDirectView({ onClose }: { onClose: () => void }) {
  const [cfg, setCfg] = useState<AiConfigResult | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("https://api.deepseek.com");
  const [model, setModel] = useState("deepseek-chat");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // 读取已保存的配置
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await getApiClient().getAiConfig();
        if (!alive) return;
        setCfg(res);
        if (res.base_url) setBaseUrl(res.base_url);
        if (res.model) setModel(res.model);
      } catch (e) {
        console.error("[ai_config]", e);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  async function handleSave() {
    if (busy) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await getApiClient().setAiConfig(apiKey.trim(), baseUrl.trim(), model.trim());
      if (res.ok) {
        setCfg(res);
        if (res.available) {
          setMsg({ type: "success", text: "AI 接口连接成功！朝廷廷议、名臣奏对与史实推演已就绪。" });
        } else {
          setMsg({ type: "error", text: "配置已保存，但连通性探测失败：请检查 API Key、Base URL 或网络代理。" });
        }
      } else {
        setMsg({ type: "error", text: "保存配置失败，请确认后端服务运行正常。" });
      }
    } catch (e) {
      console.error("[setAiConfig]", e);
      setMsg({ type: "error", text: "配置失败：" + (e instanceof Error ? e.message : String(e)) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3.5">
      {/* 预设快捷填入 */}
      <div>
        <div className="mb-1.5 flex items-center gap-1 font-kai text-xs text-dim">
          <Sparkles size={12} className="text-goldDark" /> 常用服务商一键配置：
        </div>
        <div className="grid grid-cols-3 gap-2">
          {PROVIDER_PRESETS.map((p) => (
            <button
              key={p.name}
              onClick={() => {
                setBaseUrl(p.baseUrl);
                setModel(p.model);
              }}
              className={`rounded border p-2 text-left transition ${
                baseUrl === p.baseUrl && model === p.model
                  ? "border-red bg-red/10 shadow-sm"
                  : "border-gold/30 bg-paper/60 hover:border-gold hover:bg-gold-light/30"
              }`}
            >
              <div className="font-kai text-xs font-bold text-ink">{p.name}</div>
              <div className="mt-0.5 line-clamp-1 font-sans text-[10px] text-dim">{p.model}</div>
            </button>
          ))}
        </div>
      </div>

      {/* 核心表单区 */}
      <div className="space-y-3 rounded-lg border border-gold/40 bg-paper/60 p-4 shadow-paper">
        {/* API Key */}
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="font-kai font-medium text-ink">API Key（密钥）</span>
            <span className="font-sans text-[11px] text-dim">
              {cfg?.has_key ? "（已配置生效）" : "（未配置）"}
            </span>
          </div>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={cfg?.has_key ? "留空则保持现有密钥不变，输入则更新覆盖" : "输入 sk-... 密钥"}
            className="w-full rounded border border-gold/40 bg-card px-3 py-1.5 font-sans text-sm text-ink outline-none focus:border-red"
          />
        </div>

        {/* Base URL */}
        <div className="space-y-1">
          <span className="font-kai text-xs font-medium text-ink">Base URL（接口端点地址）</span>
          <input
            type="text"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://api.deepseek.com 或 https://api.openai.com/v1"
            className="w-full rounded border border-gold/40 bg-card px-3 py-1.5 font-sans text-sm text-ink outline-none focus:border-red"
          />
        </div>

        {/* Model */}
        <div className="space-y-1">
          <span className="font-kai text-xs font-medium text-ink">Model（大模型名称）</span>
          <input
            type="text"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="deepseek-chat 或 gpt-4o-mini"
            className="w-full rounded border border-gold/40 bg-card px-3 py-1.5 font-sans text-sm text-ink outline-none focus:border-red"
          />
        </div>
      </div>

      {/* 状态与反馈 */}
      {msg && (
        <div
          className={`flex items-start gap-2 rounded-lg border p-3 text-xs leading-relaxed font-kai ${
            msg.type === "success"
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-800"
              : "border-red/40 bg-red/10 text-red-dark"
          }`}
        >
          {msg.type === "success" ? (
            <CheckCircle2 size={16} className="shrink-0 text-emerald-600 mt-0.5" />
          ) : (
            <AlertCircle size={16} className="shrink-0 text-red mt-0.5" />
          )}
          <span>{msg.text}</span>
        </div>
      )}

      {/* 操作按钮区 */}
      <div className="flex items-center justify-between pt-1">
        <button
          onClick={onClose}
          className="rounded border border-gold/40 bg-paper/60 px-4 py-1.5 font-kai text-xs text-ink transition hover:bg-gold-light"
        >
          关闭
        </button>
        <button
          onClick={handleSave}
          disabled={busy}
          className="flex items-center gap-2 rounded-lg bg-red px-6 py-2 font-kai text-sm font-bold tracking-widest text-paper shadow-card transition hover:bg-red-dark disabled:opacity-50"
        >
          {busy && <Loader2 size={15} className="animate-spin" />}
          {busy ? "连通探测中…" : "保存并测试连接"}
        </button>
      </div>
    </div>
  );
}

/** 音律与杂项设置 */
function AudioSettingsView() {
  const [muted, setMuted] = useState(false);
  const [vol, setVol] = useState(75);

  return (
    <div className="space-y-4 rounded-lg border border-gold/40 bg-paper/60 p-4 font-kai">
      <div className="space-y-2">
        <div className="flex justify-between text-sm text-ink">
          <span>大晟府雅乐音量</span>
          <span>{muted ? "静音" : `${vol}%`}</span>
        </div>
        <input
          type="range"
          min="0"
          max="100"
          value={muted ? 0 : vol}
          onChange={(e) => {
            setVol(Number(e.target.value));
            setMuted(false);
          }}
          className="w-full accent-red"
        />
      </div>

      <label className="flex items-center gap-2 text-sm text-ink cursor-pointer pt-2">
        <input
          type="checkbox"
          checked={muted}
          onChange={(e) => setMuted(e.target.checked)}
          className="accent-red"
        />
        <span>静音（关闭全盘背景古乐与音效）</span>
      </label>
    </div>
  );
}
