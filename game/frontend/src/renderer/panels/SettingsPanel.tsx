import { useEffect, useState, useRef } from "react";
import { Loader2, Bot, Volume2, CheckCircle2, AlertCircle, Sparkles, RefreshCw, ChevronDown, Type } from "lucide-react";
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
  const [tab, setTab] = useState<"ai" | "audio" | "ui">("ai");
  const popOverlay = useGameStore((s) => s.popOverlay);
  const pushOverlay = useGameStore((s) => s.pushOverlay);
  const clearOverlays = useGameStore((s) => s.clearOverlays);
  const setInGame = useGameStore((s) => s.setInGame);
  const inGame = useGameStore((s) => s.inGame);

  // 迁移补齐（原 Tk `_ui_back_to_menu` / panels_meta 设置入口列表）：
  // 返回主菜单 = 三选一确认（先存档 / 直接回 / 取消），此处用两次确认等价表达。
  async function backToMenu() {
    const saveFirst = window.confirm(
      "返回主菜单前是否先存档？\n\n【确定】= 先存档再回主菜单\n【取消】= 不存档，直接回主菜单"
    );
    if (saveFirst) {
      try {
        const res = await getApiClient().save(0);
        if (!res.ok && !window.confirm("自动存档失败（槽位 0）。仍要返回主菜单吗？")) return;
      } catch {
        if (!window.confirm("自动存档失败（槽位 0 写入异常）。仍要返回主菜单吗？")) return;
      }
    }
    clearOverlays();
    setInGame(false);
  }

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
          <button
            onClick={() => setTab("ui")}
            className={`flex items-center gap-1.5 rounded px-3 py-1 font-kai text-sm transition ${
              tab === "ui"
                ? "bg-red text-paper shadow-sm"
                : "bg-paper/70 text-ink hover:bg-gold-light/40"
            }`}
          >
            <Type size={15} /> 界面字号
          </button>
        </div>
        <span className="font-kai text-xs text-dim">
          {tab === "ai"
            ? "自定义接口 · 智能模型识别"
            : tab === "audio"
              ? "大晟府雅乐 · 环境音律规制"
              : "字号档位 · 对齐 Tk 设置"}
        </span>
      </div>

      {/* 迁移补齐：设置面板入口列表（原 Tk panels_meta `_panel_misc`/`_panel_settings`）
          —— 存档·读档（SavePanel 此前无入口）/ Token 用量 / 返回主菜单 */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => pushOverlay({ kind: "save", title: "存档 · 读档" })}
          className="rounded border border-gold/50 bg-paper/70 px-3 py-1 font-kai text-xs text-ink transition hover:bg-gold-light/40"
        >
          存档 · 读档
        </button>
        <button
          onClick={() => pushOverlay({ kind: "meter", title: "Token 用量" })}
          className="rounded border border-gold/50 bg-paper/70 px-3 py-1 font-kai text-xs text-ink transition hover:bg-gold-light/40"
        >
          Token 用量
        </button>
        {inGame && (
          <button
            onClick={backToMenu}
            className="rounded border border-red/50 bg-paper/70 px-3 py-1 font-kai text-xs text-red transition hover:bg-red/10"
          >
            返回主菜单
          </button>
        )}
      </div>

      {tab === "ai" ? (
        <AiConfigDirectView onClose={popOverlay} />
      ) : tab === "audio" ? (
        <AudioSettingsView />
      ) : (
        <UiScaleSettingsView />
      )}
    </div>
  );
}

/** 智能 AI 配置核心表单（支持自定义接口与模型自动识别） */
function AiConfigDirectView({ onClose }: { onClose: () => void }) {
  const [cfg, setCfg] = useState<AiConfigResult | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("https://api.deepseek.com");
  const [model, setModel] = useState("deepseek-chat");
  const [activePreset, setActivePreset] = useState<string>("DeepSeek 官方");

  const baseUrlRef = useRef<HTMLInputElement>(null);
  const apiKeyRef = useRef<HTMLInputElement>(null);

  // 模型自动识别列表
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [fetchingModels, setFetchingModels] = useState(false);

  const [busy, setBusy] = useState(false);
  // 迁移补齐：大臣办差工具（function calling）三档（对齐 Tk 设置面板 auto/on/off）
  const [enableTools, setEnableTools] = useState("auto");
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
        if (res.enable_tools) setEnableTools(res.enable_tools);
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
      const res = await getApiClient().setAiConfig(
        apiKey.trim(), baseUrl.trim(), model.trim(), enableTools);
      if (res.ok) {
        // D 修复：setAiConfig 的返回体不含 has_key/configured/api_key_masked，
        // 原 `setCfg(res as any)` 整体覆盖 → 保存后界面会错误显示「（未配置）」，
        // 直到重新拉取。现改为保存成功后回读权威配置（失败则保留旧值）。
        try {
          const fresh = await getApiClient().getAiConfig();
          setCfg(fresh);
        } catch (cfgErr) {
          console.warn("[setAiConfig] 回读配置失败，沿用原配置：", cfgErr);
        }
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
          {PROVIDER_PRESETS.map((p) => {
            const isSelected = activePreset === p.name;
            return (
              <button
                key={p.name}
                type="button"
                onClick={() => {
                  setActivePreset(p.name);
                  if (p.name.includes("自定义")) {
                    // 点击自定义时：若当前仍是官方地址则清空，并自动光标聚焦到 Base URL 输入框
                    if (baseUrl === "https://api.deepseek.com" || baseUrl === "https://api.openai.com/v1" || baseUrl.includes("11434")) {
                      setBaseUrl("");
                      setModel("");
                    }
                    setTimeout(() => baseUrlRef.current?.focus(), 50);
                    setMsg({ type: "success", text: "已切换为自定义中转站模式，请在下方输入您的接口地址与模型。" });
                  } else {
                    setBaseUrl(p.baseUrl);
                    setModel(p.model);
                    setMsg(null);
                  }
                }}
                className={`rounded border p-2 text-left transition cursor-pointer ${
                  isSelected
                    ? "border-red bg-red/15 shadow-sm ring-1 ring-red/50"
                    : "border-gold/40 bg-paper/70 hover:border-gold hover:bg-gold-light/40"
                }`}
              >
                <div className={`font-kai text-xs font-bold truncate ${isSelected ? "text-red-dark" : "text-ink"}`}>
                  {p.name}
                </div>
                <div className="mt-0.5 line-clamp-1 font-sans text-[10px] text-dim">
                  {p.model || "支持任意网关"}
                </div>
              </button>
            );
          })}
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
            ref={baseUrlRef}
            type="text"
            value={baseUrl}
            onChange={(e) => {
              setBaseUrl(e.target.value);
              setActivePreset("自定义中转站 / OneAPI");
            }}
            placeholder="如：https://api.deepseek.com 或 https://your-proxy.com/v1"
            className="w-full rounded border border-gold/40 bg-card px-3 py-1.5 font-sans text-sm text-ink outline-none focus:border-red"
          />
        </div>

        {/* Model 与 纯图标识别按钮 */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs">
            <span className="font-kai font-medium text-ink">Model（大模型名称）</span>
            {/* 自动识别模型：仅保留精致纯图标 */}
            <button
              onClick={handleFetchModels}
              disabled={fetchingModels}
              title="自动探测并识别该接口下的可用模型列表"
              className="group flex h-6 w-6 items-center justify-center rounded border border-gold/50 bg-paper text-goldDark transition hover:border-red hover:bg-gold-light/40 hover:text-red disabled:opacity-50"
            >
              {fetchingModels ? (
                <Loader2 size={13} className="animate-spin text-red" />
              ) : (
                <RefreshCw size={13} className="transition group-hover:rotate-90" />
              )}
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

        {/* 迁移补齐：大臣办差工具三档（对齐 Tk 设置面板 auto/on/off） */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs">
            <span className="font-kai font-medium text-ink">大臣办差工具（function calling）</span>
            <span className="font-sans text-[10px] text-dim">
              自动＝按端点探测；关闭＝纯文本契约
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {([["auto", "自动（探测端点）"], ["on", "强制开启"], ["off", "关闭"]] as const).map(
              ([val, label]) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => setEnableTools(val)}
                  className={`rounded border px-2.5 py-1 font-kai text-xs transition ${
                    enableTools === val
                      ? "border-red bg-red/10 text-red-dark"
                      : "border-gold/40 bg-paper/70 text-ink hover:bg-gold-light/40"
                  }`}
                >
                  {label}
                </button>
              )
            )}
          </div>
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

const SCALE_KEY = "songzuo_font_scale";
const SCALE_TABLE: Record<number, { label: string; html: number }> = {
  1: { label: "小", html: 14 },
  2: { label: "中", html: 15 },
  3: { label: "大", html: 17 },
  4: { label: "特大", html: 19 },
};

/** 界面字体族（迁移补齐：原 Tk `_panel_misc` 的字体切换；
 *  Web 以系统字族 + 运行时覆盖 `.font-kai` 实现，localStorage 持久化）。 */
const FONT_KEY = "sz:fontFamily";
const FONT_TABLE: Record<string, { label: string; css: string }> = {
  "楷体": { label: "楷体（默认）", css: '"KaiTi","STKaiti","楷体","Source Han Serif SC",serif' },
  "宋体": { label: "宋体", css: '"SimSun","Songti SC","STSong","宋体",serif' },
  "黑体": { label: "黑体", css: '"SimHei","Heiti SC","黑体",sans-serif' },
  "雅黑": { label: "雅黑", css: '"Microsoft YaHei","微软雅黑","PingFang SC",sans-serif' },
  "系统": { label: "系统默认", css: 'system-ui,-apple-system,"Segoe UI",sans-serif' }
};

function applyFontFamily(key: string) {
  const t = FONT_TABLE[key] ?? FONT_TABLE["楷体"];
  let el = document.getElementById("sz-font-override") as HTMLStyleElement | null;
  if (!el) {
    el = document.createElement("style");
    el.id = "sz-font-override";
    document.head.appendChild(el);
  }
  el.textContent = `.font-kai{font-family:${t.css} !important;}`;
  localStorage.setItem(FONT_KEY, key);
}

/** 界面字号档位（对齐 Tk _panel_misc font_scale；localStorage 持久化 + html 根字号） */
function UiScaleSettingsView() {
  const [scale, setScale] = useState(() => {
    const raw = Number(localStorage.getItem(SCALE_KEY) || 2);
    return SCALE_TABLE[raw] ? raw : 2;
  });

  function apply(next: number) {
    setScale(next);
    localStorage.setItem(SCALE_KEY, String(next));
    document.documentElement.style.fontSize = `${SCALE_TABLE[next].html}px`;
  }

  // 字体族（迁移补齐）：读取本地偏好并在挂载时应用
  const [fontFamily, setFontFamily] = useState(() => {
    const k = localStorage.getItem(FONT_KEY) || "楷体";
    return FONT_TABLE[k] ? k : "楷体";
  });

  useEffect(() => {
    document.documentElement.style.fontSize = `${SCALE_TABLE[scale].html}px`;
    applyFontFamily(localStorage.getItem(FONT_KEY) || "楷体");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-4 rounded-lg border border-gold/40 bg-paper/60 p-4 font-kai">
      <div>
        <p className="text-sm font-bold text-ink">界面字号</p>
        <p className="mt-0.5 text-xs text-dim">
          档位：小 / 中 / 大 / 特大（写入本地偏好，刷新后仍生效）
        </p>
      </div>
      <div className="flex gap-2">
        {Object.entries(SCALE_TABLE).map(([k, v]) => {
          const n = Number(k);
          return (
            <button
              key={k}
              onClick={() => apply(n)}
              className={`rounded px-4 py-1.5 text-sm transition ${
                scale === n
                  ? "bg-red text-paper shadow-sm"
                  : "border border-gold/50 bg-card text-ink hover:bg-gold-light/40"
              }`}
            >
              {v.label}
            </button>
          );
        })}
      </div>
      <p className="text-xs text-dim">
        当前：{SCALE_TABLE[scale].label}（基准 {SCALE_TABLE[scale].html}px）
      </p>

      {/* 迁移补齐：正文字族切换（原 Tk `_panel_misc` 字体档） */}
      <div className="border-t border-gold/30 pt-3">
        <p className="text-sm font-bold text-ink">界面字体</p>
        <p className="mt-0.5 text-xs text-dim">
          正文字族：楷体 / 宋体 / 黑体 / 雅黑 / 系统默认（写入本地偏好，刷新后仍生效）
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          {Object.entries(FONT_TABLE).map(([k, v]) => (
            <button
              key={k}
              onClick={() => {
                setFontFamily(k);
                applyFontFamily(k);
              }}
              className={`rounded px-3 py-1.5 text-sm transition ${
                fontFamily === k
                  ? "bg-red text-paper shadow-sm"
                  : "border border-gold/50 bg-card text-ink hover:bg-gold-light/40"
              }`}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

