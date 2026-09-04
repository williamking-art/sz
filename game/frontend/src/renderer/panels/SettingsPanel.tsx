import { useEffect, useState } from "react";
import { Loader2, Bot, Volume2, CheckCircle2, AlertCircle, Sparkles, RefreshCw, ChevronDown } from "lucide-react";
import { getApiClient, type AiConfigResult } from "../api/client";
import { useGameStore } from "../store/gameStore";

// 常见大模型服务商快捷预设
const PROVIDER_PRESETS = [
  {
    name: "DeepSeek 官方",
    baseUrl: "https://api.deepseek.com",
    model: "deepseek-chat",
    desc: "北宋史实与朝堂奏对推荐"
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
    desc: "离线本地运行，免外网 Key"
  },
  {
    name: "自定义中转站 / OneAPI",
    baseUrl: "",
    model: "",
    desc: "支持任意兼容 OpenAI 规范的聚合网关"
  }
];

export default function SettingsPanel() {
  const [tab, setTab] = useState<"ai" | "audio">("ai");
  const popOverlay = useGameStore((s) => s.popOverlay);

  return (
    <div className="space-y-4">
      {/* 顶部直达 Tab */}
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
          {tab === "ai" ? "自定义接口 · 智能模型识别" : "大晟府雅乐 · 环境音律规制"}
        </span>
      </div>

      {tab === "ai" ? <AiConfigDirectView onClose={popOverlay} /> : <AudioSettingsView />}
    </div>
  );
}

/** 智能 AI 配置核心表单（支持自定义接口与模型自动识别） */
function AiConfigDirectView({ onClose }: { onClose: () => void }) {
  const [cfg, setCfg] = useState<AiConfigResult | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("https://api.deepseek.com");
  const [model, setModel] = useState("deepseek-chat");

  // 模型自动识别列表
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [fetchingModels, setFetchingModels] = useState(false);

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

  // 自动探测并识别该接口下的所有可用模型
  async function handleFetchModels() {
    if (fetchingModels) return;
    setFetchingModels(true);
    setMsg(null);
    try {
      const res = await getApiClient().fetchModels(apiKey.trim(), baseUrl.trim());
      if (res.ok && res.models && res.models.length > 0) {
        setAvailableModels(res.models);
        // 如果当前模型不在列表里，默认选第一个
        if (!res.models.includes(model)) {
          setModel(res.models[0]);
        }
        setMsg({ type: "success", text: `成功识别出 ${res.models.length} 个可用模型，请在下方点击或下拉选择。` });
      } else {
        setMsg({ type: "error", text: "未能从该接口拉取到模型列表，请确认 Key 与 Base URL 是否正确。" });
      }
    } catch (e) {
      setMsg({ type: "error", text: "探测模型列表失败：" + (e instanceof Error ? e.message : String(e)) });
    } finally {
      setFetchingModels(false);
    }
  }

  // 保存并强制在线自检
  async function handleSave() {
    if (busy) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await getApiClient().setAiConfig(apiKey.trim(), baseUrl.trim(), model.trim());
      if (res.ok) {
        setCfg(res as any);
        if (res.available) {
          setMsg({ type: "success", text: `AI 接口连接成功！${res.message || `当前模型【${model}】在线自检通过。`}` });
        } else {
          setMsg({ type: "error", text: `配置已保存，但连通自检未通过：${res.message || "请检查密钥、地址或模型名称。"}` });
        }
      } else {
        setMsg({ type: "error", text: "保存配置失败，请确认后端服务运行正常。" });
      }
    } catch (e) {
      console.error("[setAiConfig]", e);
      setMsg({ type: "error", text: "保存失败：" + (e instanceof Error ? e.message : String(e)) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3.5">
      {/* 预设与自定义快捷切换 */}
      <div>
        <div className="mb-1.5 flex items-center justify-between font-kai text-xs text-dim">
          <span className="flex items-center gap-1">
            <Sparkles size={12} className="text-goldDark" /> 服务商快捷模版（点击自动预填）：
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {PROVIDER_PRESETS.map((p) => (
            <button
              key={p.name}
              onClick={() => {
                if (p.baseUrl) setBaseUrl(p.baseUrl);
                if (p.model) setModel(p.model);
              }}
              className={`rounded border p-2 text-left transition ${
                baseUrl === p.baseUrl && model === p.model
                  ? "border-red bg-red/10 shadow-sm"
                  : "border-gold/30 bg-paper/60 hover:border-gold hover:bg-gold-light/30"
              }`}
            >
              <div className="font-kai text-xs font-bold text-ink truncate">{p.name}</div>
              <div className="mt-0.5 line-clamp-1 font-sans text-[10px] text-dim">{p.model || "自定义地址"}</div>
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
            placeholder={cfg?.has_key ? "保持留空则使用已保存密钥，输入则更新覆盖" : "输入 sk-... 密钥"}
            className="w-full rounded border border-gold/40 bg-card px-3 py-1.5 font-sans text-sm text-ink outline-none focus:border-red"
          />
        </div>

        {/* Base URL (支持自定义接口) */}
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="font-kai font-medium text-ink">Base URL（自定义接口地址）</span>
            <span className="font-sans text-[10px] text-dim">支持任意自定义中转 / OneAPI / 本地网关</span>
          </div>
          <input
            type="text"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="如：https://api.deepseek.com 或 https://your-proxy.com/v1"
            className="w-full rounded border border-gold/40 bg-card px-3 py-1.5 font-sans text-sm text-ink outline-none focus:border-red"
          />
        </div>

        {/* Model 与 智能识别按钮 */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs">
            <span className="font-kai font-medium text-ink">Model（大模型名称）</span>
            {/* 自动识别模型大按钮 */}
            <button
              onClick={handleFetchModels}
              disabled={fetchingModels}
              className="flex items-center gap-1 rounded bg-gold/20 px-2 py-0.5 font-kai text-xs text-goldDark transition hover:bg-gold/30 disabled:opacity-50"
            >
              {fetchingModels ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
              {fetchingModels ? "正在识别中…" : "🔍 自动探测识别模型列表"}
            </button>
          </div>

          <div className="relative">
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="如 deepseek-chat 或 qwen-plus"
              className="w-full rounded border border-gold/40 bg-card px-3 py-1.5 font-sans text-sm text-ink outline-none focus:border-red"
            />
          </div>

          {/* 若识别成功，展示快捷可选模型胶囊 */}
          {availableModels.length > 0 && (
            <div className="mt-2 space-y-1 rounded border border-gold/30 bg-card/70 p-2 text-xs">
              <div className="font-kai text-[11px] text-dim">接口已识别可用模型（点击直接选择）：</div>
              <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto pr-1">
                {availableModels.map((m) => (
                  <button
                    key={m}
                    onClick={() => setModel(m)}
                    className={`rounded px-2 py-0.5 font-sans text-[11px] transition ${
                      model === m
                        ? "bg-red text-paper shadow-sm"
                        : "bg-paper text-ink-light hover:bg-gold-light hover:text-ink"
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 状态与反馈信息 */}
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
          {busy ? "连通测试中…" : "保存并在线自检"}
        </button>
      </div>
    </div>
  );
}

/** 视听音律设置 */
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
