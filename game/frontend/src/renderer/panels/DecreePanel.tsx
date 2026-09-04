import { useState } from "react";
import { Loader2, PenLine, Scroll, Send, Sparkles } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore } from "../store/gameStore";

// 常见拟旨范例模板（点击一键填入）
const DECREE_TEMPLATES = [
  { label: "免灾赈民", text: "敕：两浙、江南诸路频遭水患，特除免今岁夏秋两税积欠，开常平仓出陈粮赈济流民，督办有司毋得迁延。" },
  { label: "开海市舶", text: "敕：广南东路广州市舶司、两浙明州各增置海舶榷场，优假外夷商贾，通互市以阜国用。" },
  { label: "治河防汛", text: "敕：工部遣员督领夫役，修浚黄河故道堤防，拨内帑钱五万贯以佐经费。" },
  { label: "严防北境", text: "敕：河北、河东缘边诸军整肃戎备，加固真定、大名城防，谍探北朝动向，毋得轻举妄动。" },
];

interface ProcDef {
  key: string;
  label: string;
  fields: { key: string; label: string; type: "text" | "number"; def: string }[];
}

const PROCEDURES: ProcDef[] = [
  {
    key: "fixed_finance",
    label: "钱粮调度",
    fields: [
      { key: "source", label: "调出仓府", type: "text", def: "国库" },
      { key: "target", label: "拨往去处", type: "text", def: "开封府" },
      { key: "amount", label: "拨发数额（贯/石）", type: "number", def: "20000" }
    ]
  },
  {
    key: "fixed_tech",
    label: "军工科技",
    fields: [
      { key: "project", label: "营缮项目", type: "text", def: "改良水运翻车" },
      { key: "invest", label: "度支投入（贯）", type: "number", def: "10000" },
      { key: "months", label: "督造工期（月）", type: "number", def: "6" }
    ]
  },
  {
    key: "fixed_construction",
    label: "水利营造",
    fields: [
      { key: "site", label: "营建州郡", type: "text", def: "扬州" },
      { key: "kind", label: "工程门类", type: "text", def: "疏浚运河" },
      { key: "invest", label: "调拨工费（贯）", type: "number", def: "20000" },
      { key: "months", label: "预计工期（月）", type: "number", def: "12" }
    ]
  },
  {
    key: "fixed_army",
    label: "边防调戍",
    fields: [
      { key: "army", label: "移防军号", type: "text", def: "殿前司捧日军" },
      { key: "to_line", label: "驻防阵线", type: "text", def: "北线_真定河间" },
      { key: "scale", label: "调发兵额（人）", type: "number", def: "2000" }
    ]
  }
];

export default function DecreePanel() {
  const [mode, setMode] = useState<"free" | "fixed">("free");
  // 自由拟旨输入
  const [freeText, setFreeText] = useState("");
  const [title, setTitle] = useState("");
  const [minister, setMinister] = useState("");
  const [secret, setSecret] = useState(false);

  // 固定政务输入
  const [cat, setCat] = useState(PROCEDURES[0].key);
  const [fixedValues, setFixedValues] = useState<Record<string, string>>({});

  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const setState = useGameStore((s) => s.setState);

  const proc = PROCEDURES.find((p) => p.key === cat)!;

  function valOf(f: ProcDef["fields"][number]): string {
    return fixedValues[`${cat}.${f.key}`] ?? f.def;
  }

  async function submitFree() {
    if (busy || !freeText.trim()) return;
    setBusy(true);
    setResult(null);

    try {
      const res = await getApiClient().action("issue_decree", {
        text: freeText.trim(),
        title: title.trim() || "御前诏敕",
        minister: minister.trim() || "有司",
        is_secret: secret
      });
      if (res.state) setState(res.state);
      setResult(res.message || "诏敕已传宣尚书省，有司领旨奉行。");
      setFreeText("");
      setTitle("");
    } catch (e) {
      console.error("[issue_decree]", e);
      try {
        const fallbackRes = await getApiClient().action("issue_free_decree", {
          parse_result: {
            category: "custom",
            exec_mode: "instant",
            title: title.trim() || "御前特旨",
            text: freeText.trim()
          },
          minister: minister.trim() || "中书门下",
          is_secret: secret
        });
        if (fallbackRes.state) setState(fallbackRes.state);
        setResult(fallbackRes.message || "圣旨已下发中枢门下，候朝堂推演施行。");
        setFreeText("");
      } catch (err2) {
        setResult("拟旨未成：" + (e instanceof Error ? e.message : String(e)));
      }
    } finally {
      setBusy(false);
    }
  }

  async function submitFixed() {
    if (busy) return;
    setBusy(true);
    setResult(null);
    const params: Record<string, string | number> = {};
    for (const f of proc.fields) {
      const raw = valOf(f);
      params[f.key] = f.type === "number" ? Number(raw || 0) : raw;
    }
    const parseResult = {
      category: cat,
      exec_mode: "longterm",
      title: title.trim() || proc.label,
      params
    };
    try {
      const res = await getApiClient().action("issue_free_decree", {
        parse_result: parseResult,
        minister: minister.trim() || "有司",
        is_secret: secret
      });
      if (res.state) setState(res.state);
      setResult(res.message || "旨意已成定例，列入在办政务。");
    } catch (e) {
      console.error("[issue_fixed]", e);
      setResult("颁行政务失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* 模式切换：亲笔拟旨 / 常设政务 */}
      <div className="flex items-center justify-between border-b border-gold/40 pb-2">
        <div className="flex gap-2">
          <button
            onClick={() => setMode("free")}
            className={`flex items-center gap-1.5 rounded px-3 py-1 font-kai text-sm transition ${
              mode === "free"
                ? "bg-red text-paper shadow-sm"
                : "bg-paper/70 text-ink hover:bg-gold-light/40"
            }`}
          >
            <PenLine size={14} /> 亲笔拟旨
          </button>
          <button
            onClick={() => setMode("fixed")}
            className={`flex items-center gap-1.5 rounded px-3 py-1 font-kai text-sm transition ${
              mode === "fixed"
                ? "bg-red text-paper shadow-sm"
                : "bg-paper/70 text-ink hover:bg-gold-light/40"
            }`}
          >
            <Scroll size={14} /> 常设政务
          </button>
        </div>
        <span className="font-kai text-xs text-dim">
          {mode === "free" ? "乾纲独断 · 言出法随" : "例行公文 · 规制常设"}
        </span>
      </div>

      {mode === "free" ? (
        /* ==== 自由拟旨模式（自由打字） ==== */
        <div className="space-y-3">
          {/* 圣旨大书写区 */}
          <div className="edict-paper relative rounded-lg p-4">
            <div className="mb-2 flex items-center justify-between border-b border-gold/30 pb-1.5">
              <span className="font-kai text-sm font-bold tracking-widest text-red-dark">
                【皇帝制曰 · 御前丹诏】
              </span>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="诏令标题（如：宽免二税诏）"
                className="w-48 rounded border border-gold/40 bg-card/60 px-2 py-0.5 font-kai text-xs text-ink outline-none focus:border-red"
              />
            </div>

            <textarea
              value={freeText}
              onChange={(e) => setFreeText(e.target.value)}
              rows={5}
              placeholder="在此亲笔书写圣旨正文……（例：门下：比岁灾歉，民食维艰，朕甚悯焉。其两浙、江南诸路积欠免除二分，出内帑三万贯赈抚流民，有司敬听奉行。）"
              className="w-full resize-none bg-transparent font-kai text-[15px] leading-relaxed tracking-wide text-ink placeholder:text-dim/60 outline-none"
              autoFocus
            />

            <div className="mt-2 flex items-center justify-between border-t border-gold/20 pt-2 text-xs">
              <span className="font-kai text-dim">字数：{freeText.length} 字</span>
              <div className="flex items-center gap-4">
                <input
                  type="text"
                  value={minister}
                  onChange={(e) => setMinister(e.target.value)}
                  placeholder="督办重臣（默认中书省）"
                  className="w-36 rounded border border-gold/30 bg-card/60 px-2 py-0.5 font-kai text-xs text-ink outline-none"
                />
                <label className="flex cursor-pointer items-center gap-1.5 font-kai text-ink">
                  <input
                    type="checkbox"
                    checked={secret}
                    onChange={(e) => setSecret(e.target.checked)}
                    className="accent-red"
                  />
                  <span>御前密谕</span>
                </label>
              </div>
            </div>
          </div>

          {/* 典籍范例快捷填入 */}
          <div>
            <div className="mb-1.5 flex items-center gap-1 font-kai text-xs text-dim">
              <Sparkles size={12} className="text-goldDark" /> 朝廷常用诏令范本（点击速填）：
            </div>
            <div className="grid grid-cols-2 gap-2">
              {DECREE_TEMPLATES.map((tpl) => (
                <button
                  key={tpl.label}
                  onClick={() => {
                    setTitle(`${tpl.label}诏`);
                    setFreeText(tpl.text);
                  }}
                  className="rounded border border-gold/30 bg-paper/60 p-2 text-left transition hover:border-gold hover:bg-gold-light/30"
                >
                  <div className="font-kai text-xs font-bold text-red">{tpl.label}</div>
                  <div className="mt-0.5 line-clamp-1 font-kai text-[11px] text-dim">{tpl.text}</div>
                </button>
              ))}
            </div>
          </div>

          {/* 颁布大按钮 */}
          <div className="flex justify-end pt-1">
            <button
              onClick={submitFree}
              disabled={busy || !freeText.trim()}
              className="flex items-center gap-2 rounded-lg bg-red px-8 py-2 font-kai text-base tracking-widest text-paper shadow-card transition hover:bg-red-dark disabled:opacity-50"
            >
              {busy ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              {busy ? "宣谕中…" : "奉天颁行"}
            </button>
          </div>
        </div>
      ) : (
        /* ==== 常规政务模式 ==== */
        <div className="space-y-3">
          <div className="flex flex-wrap gap-1.5">
            {PROCEDURES.map((p) => (
              <button
                key={p.key}
                onClick={() => setCat(p.key)}
                className={`rounded px-2.5 py-1 font-kai text-xs transition ${
                  cat === p.key ? "bg-red text-paper shadow-sm" : "bg-paper/70 text-ink hover:bg-gold-light/40"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          <div className="space-y-2.5 rounded-lg border border-gold/40 bg-paper/60 p-3.5">
            <Field label="政务标题" value={title} onChange={setTitle} placeholder={proc.label} />
            {proc.fields.map((f) => (
              <Field
                key={f.key}
                label={f.label}
                value={valOf(f)}
                onChange={(v) => setFixedValues((s) => ({ ...s, [`${cat}.${f.key}`]: v }))}
                type={f.type}
              />
            ))}
            <Field label="督办官署" value={minister} onChange={setMinister} placeholder="有司" />
          </div>

          <div className="flex justify-end pt-1">
            <button
              onClick={submitFixed}
              disabled={busy}
              className="flex items-center gap-2 rounded-lg bg-red px-6 py-2 font-kai text-base tracking-widest text-paper shadow-card transition hover:bg-red-dark disabled:opacity-50"
            >
              {busy && <Loader2 size={16} className="animate-spin" />}
              {busy ? "移交有司…" : "登记施行政务"}
            </button>
          </div>
        </div>
      )}

      {/* 结果反馈 */}
      {result && (
        <div className="rounded-lg border border-gold/60 bg-card p-3 shadow-paper">
          <p className="whitespace-pre-wrap font-kai text-sm leading-relaxed text-ink">{result}</p>
        </div>
      )}
    </div>
  );
}

function Field({
  label, value, onChange, placeholder, type = "text"
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: "text" | "number";
}) {
  return (
    <label className="flex items-center gap-2 text-xs">
      <span className="w-24 shrink-0 font-kai text-ink-light">{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="flex-1 rounded border border-gold/40 bg-card px-2.5 py-1 text-xs text-ink outline-none focus:border-red"
      />
    </label>
  );
}
