import { useState } from "react";
import { Loader2, Info } from "lucide-react";
import { getApiClient } from "../api/client";
import { useGameStore } from "../store/gameStore";

// 拟旨面板：固定程序四类（纯规则，不依赖 AI）+ 自由拟旨（需 AI 解析）
// 参数模板对齐 game/content/data.py::FIXED_PROCEDURES
// 落地路径：/api/action → issue_free_decree → core/commands_decree.py::issue_free_decree
interface ProcDef {
  key: string;
  label: string;
  fields: { key: string; label: string; type: "text" | "number"; def: string }[];
}

const PROCEDURES: ProcDef[] = [
  {
    key: "fixed_tech",
    label: "科技营缮",
    fields: [
      { key: "project", label: "项目", type: "text", def: "" },
      { key: "invest", label: "投入（贯）", type: "number", def: "10000" },
      { key: "months", label: "工期（月）", type: "number", def: "12" }
    ]
  },
  {
    key: "fixed_finance",
    label: "钱粮调度",
    fields: [
      { key: "source", label: "来源", type: "text", def: "国库" },
      { key: "target", label: "去向", type: "text", def: "" },
      { key: "amount", label: "数额（贯）", type: "number", def: "10000" }
    ]
  },
  {
    key: "fixed_army",
    label: "军队调动",
    fields: [
      { key: "army", label: "军队", type: "text", def: "" },
      { key: "to_line", label: "防线", type: "text", def: "" },
      { key: "scale", label: "规模", type: "number", def: "1000" }
    ]
  },
  {
    key: "fixed_construction",
    label: "工程建设",
    fields: [
      { key: "site", label: "地点", type: "text", def: "" },
      { key: "kind", label: "类型", type: "text", def: "河渠" },
      { key: "invest", label: "投入（贯）", type: "number", def: "20000" },
      { key: "months", label: "工期（月）", type: "number", def: "12" }
    ]
  }
];

export default function DecreePanel() {
  const [cat, setCat] = useState(PROCEDURES[0].key);
  const [title, setTitle] = useState("");
  const [minister, setMinister] = useState("");
  const [secret, setSecret] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const setState = useGameStore((s) => s.setState);

  const proc = PROCEDURES.find((p) => p.key === cat)!;

  function valOf(f: ProcDef["fields"][number]): string {
    return values[`${cat}.${f.key}`] ?? f.def;
  }

  async function submit() {
    if (busy) return;
    setBusy(true);
    setResult(null);
    const params: Record<string, string | number> = {};
    for (const f of proc.fields) {
      const raw = valOf(f);
      params[f.key] = f.type === "number" ? Number(raw || 0) : raw;
    }
    // parse_result 契约（commands_decree.py::issue_free_decree 读取字段）
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
      setState(res.state);
      setResult(res.message);
    } catch (e) {
      console.error("[issue_free_decree]", e);
      setResult("拟旨失败：" + (e instanceof Error ? e.message : String(e)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* 类别择定 */}
      <div className="flex flex-wrap gap-2">
        {PROCEDURES.map((p) => (
          <button
            key={p.key}
            onClick={() => setCat(p.key)}
            className={`rounded-lg px-3 py-1.5 text-sm transition ${
              cat === p.key ? "bg-red text-paper" : "bg-paper/60 text-ink hover:bg-gold-light"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* 表单 */}
      <div className="space-y-3 rounded-lg border border-gold/40 bg-paper/60 p-4">
        <Field label="诏名" value={title} onChange={setTitle} placeholder={proc.label} />
        {proc.fields.map((f) => (
          <Field
            key={f.key}
            label={f.label}
            value={valOf(f)}
            onChange={(v) => setValues((s) => ({ ...s, [`${cat}.${f.key}`]: v }))}
            type={f.type}
          />
        ))}
        <Field label="督办" value={minister} onChange={setMinister} placeholder="有司" />
        <label className="flex items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={secret}
            onChange={(e) => setSecret(e.target.checked)}
            className="h-4 w-4 accent-red"
          />
          密旨（不入朝堂）
        </label>
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-gold/40 bg-paper/50 p-2.5 text-xs leading-relaxed text-dim">
        <Info size={14} className="mt-0.5 shrink-0" />
        <span>
          固定四类由规则直接登记为长期政务，列入左侧「在办」。
          自由拟旨（机构改制 / 自由推演）须经 AI 解析，需先在 AI 设置中配置 OpenAI 兼容 API。
        </span>
      </div>

      <div className="flex justify-end">
        <button
          onClick={submit}
          disabled={busy}
          className="flex items-center gap-2 rounded-lg bg-red px-6 py-2 font-kai text-base tracking-widest text-paper transition hover:bg-red-dark disabled:opacity-60"
        >
          {busy && <Loader2 size={16} className="animate-spin" />}
          {busy ? "颁行中…" : "颁 行"}
        </button>
      </div>

      {result && (
        <div className="rounded-lg border border-gold/40 bg-paper/60 p-3">
          <p className="whitespace-pre-wrap font-kai text-[15px] leading-relaxed text-ink">
            {result}
          </p>
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
    <label className="flex items-center gap-3">
      <span className="w-24 shrink-0 text-sm text-ink-light">{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="flex-1 rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-ink outline-none focus:border-gold"
      />
    </label>
  );
}